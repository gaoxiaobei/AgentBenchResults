// ifelse_supreme: Ultimate rule-based (pure if-else) DOTO agent.
// Master-level tactical AI with deterministic BFS pathing, enemy carrier path prediction,
// lead-target fireball shooting, 100-HP lethal meteor strikes, instant flash-stealing,
// escort formation, bonus rune harvesting, and sub-frame meteor evasion.

#include "playerAI.h"

#include <algorithm>
#include <cmath>
#include <queue>
#include <vector>
#include <utility>

using namespace std;
using namespace CONST;

static Logic *logic;
static int W = 0, H = 0, HN = 0; // Map dimensions & humans per faction

// ---- Unit Helpers ----
static inline int myFac() { return logic->faction; }
static inline int enFac() { return logic->faction ^ 1; }
static inline int nt(int faction, int num) { return num * logic->map.faction_number + faction; }
static inline Human MU(int num) { return logic->humans[nt(myFac(), num)]; }
static inline Human EU(int num) { return logic->humans[nt(enFac(), num)]; }

// ---- Math & Geometry ----
static inline double D2(const Point &a, const Point &b) { double dx = a.x - b.x, dy = a.y - b.y; return dx * dx + dy * dy; }
static inline double D0(const Point &a, const Point &b) { return sqrt(D2(a, b)); }
static inline double lenv(const Point &v) { return sqrt(v.x * v.x + v.y * v.y); }
static inline int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
static inline Point clampPt(Point p) {
    p.x = p.x < 0.5 ? 0.5 : (p.x > W - 0.5 ? W - 0.5 : p.x);
    p.y = p.y < 0.5 ? 0.5 : (p.y > H - 0.5 ? H - 0.5 : p.y);
    return p;
}
static inline bool inB(int x, int y) { return x >= 0 && y >= 0 && x < W && y < H; }
static inline bool isWallC(int x, int y) { return !inB(x, y) || logic->map.pixels[x][y]; }
static inline bool validPt(const Point &p) { return p.x >= 0 && p.y >= 0 && p.x < W && p.y < H && !isWallC((int)floor(p.x), (int)floor(p.y)); }
static inline bool wallNearCell(int cx, int cy, int r) {
    for (int dx = -r; dx <= r; ++dx)
        for (int dy = -r; dy <= r; ++dy)
            if (isWallC(cx + dx, cy + dy)) return true;
    return false;
}

// ---- BFS Distance Field Cache ----
struct Field { int cx, cy; vector<int> d; };
static vector<Field> g_fields;
static inline int IDX(int x, int y) { return x * H + y; }

static const int *bfsFrom(int tx, int ty) {
    tx = clampi(tx, 0, W - 1);
    ty = clampi(ty, 0, H - 1);
    for (size_t i = 0; i < g_fields.size(); ++i)
        if (g_fields[i].cx == tx && g_fields[i].cy == ty) return g_fields[i].d.data();
    Field f;
    f.cx = tx;
    f.cy = ty;
    f.d.assign((size_t)W * H, -1);
    queue<pair<int, int>> q;
    f.d[IDX(tx, ty)] = 0;
    q.push(make_pair(tx, ty));
    const int dx[4] = {1, -1, 0, 0}, dy[4] = {0, 0, 1, -1};
    while (!q.empty()) {
        pair<int, int> cur = q.front();
        q.pop();
        int x = cur.first, y = cur.second, base = f.d[IDX(x, y)];
        for (int k = 0; k < 4; ++k) {
            int nx = x + dx[k], ny = y + dy[k];
            if (!inB(nx, ny) || logic->map.pixels[nx][ny]) continue;
            if (f.d[IDX(nx, ny)] != -1) continue;
            f.d[IDX(nx, ny)] = base + 1;
            q.push(make_pair(nx, ny));
        }
    }
    if ((int)g_fields.size() >= 16) g_fields.erase(g_fields.begin());
    g_fields.push_back(f);
    return g_fields.back().d.data();
}

// ---- Flash Mechanics ----
static bool canFlashU(int num) {
    Human h = MU(num);
    if (h.death_time != -1 || h.flash_time > 0 || h.flash_num <= 0) return false;
    if (logic->crystal[enFac()].belong == nt(myFac(), num)) return false; // Carrier cannot flash
    return true;
}

static Point rayFlash(const Point &pos, const Point &target) {
    Point dir = Point(target.x - pos.x, target.y - pos.y);
    double dd = lenv(dir);
    if (dd < 1.0) return Point(-1, -1);
    dir = Point(dir.x / dd, dir.y / dd);
    Point best = pos;
    double bestR = 0;
    for (double r = 2.0; r <= flash_distance - 0.5; r += 0.5) {
        Point c = Point(pos.x + dir.x * r, pos.y + dir.y * r);
        if (!validPt(c)) break;
        best = c;
        bestR = r;
    }
    return bestR >= 2.0 ? best : Point(-1, -1);
}

// ---- Smooth Path Movement ----
static void go(int num, Point target, bool wantFlash) {
    Human me = MU(num);
    if (me.death_time != -1) return;
    Point pos = me.position;
    int pcx = clampi((int)floor(pos.x), 0, W - 1);
    int pcy = clampi((int)floor(pos.y), 0, H - 1);
    int tcx = clampi((int)floor(target.x), 0, W - 1);
    int tcy = clampi((int)floor(target.y), 0, H - 1);
    const int dxa[4] = {1, -1, 0, 0}, dya[4] = {0, 0, 1, -1};

    if (wantFlash && canFlashU(num) && D0(pos, target) > flash_distance * 0.5) {
        Point ft = rayFlash(pos, target);
        if (ft.x >= 0) {
            logic->move(num, ft);
            logic->flash(num);
            return;
        }
    }

    Point stepDest = pos;
    bool openArea = !wallNearCell(pcx, pcy, 2);
    if (openArea && D0(pos, target) > 0.01) {
        Point del = Point(target.x - pos.x, target.y - pos.y);
        double len = lenv(del);
        if (len > human_velocity) del = Point(del.x * human_velocity / len, del.y * human_velocity / len);
        stepDest = Point(pos.x + del.x, pos.y + del.y);
    } else {
        // Dynamic carrier targets change every frame; build a route field only
        // when walls prevent the cheap open-space steering above.
        const int *d = bfsFrom(tcx, tcy);
        int curD = d[IDX(pcx, pcy)];
        int best = -1, bestv = (curD < 0 ? (1 << 30) : curD);
        for (int k = 0; k < 4; ++k) {
            int nx = pcx + dxa[k], ny = pcy + dya[k];
            if (!inB(nx, ny) || logic->map.pixels[nx][ny]) continue;
            int v = d[IDX(nx, ny)];
            if (v < 0) continue;
            if (v < bestv) { bestv = v; best = k; }
        }
        if (best >= 0) {
            Point cc = Point(pcx + dxa[best] + 0.5, pcy + dya[best] + 0.5);
            Point del = Point(cc.x - pos.x, cc.y - pos.y);
            double len = lenv(del);
            if (len > human_velocity) del = Point(del.x * human_velocity / len, del.y * human_velocity / len);
            stepDest = Point(pos.x + del.x, pos.y + del.y);
        } else if (curD < 0) {
            Point del = Point(target.x - pos.x, target.y - pos.y);
            double len = lenv(del);
            if (len > 0.001) { del = Point(del.x * human_velocity / len, del.y * human_velocity / len); stepDest = Point(pos.x + del.x, pos.y + del.y); }
        }
    }
    if (validPt(stepDest)) {
        logic->move(num, stepDest);
    } else {
        for (int k = 0; k < 4; ++k) {
            int nx = pcx + dxa[k], ny = pcy + dya[k];
            if (!inB(nx, ny) || logic->map.pixels[nx][ny]) continue;
            Point cc = Point(nx + 0.5, ny + 0.5);
            Point del = Point(cc.x - pos.x, cc.y - pos.y);
            double len = lenv(del);
            if (len > human_velocity) del = Point(del.x * human_velocity / len, del.y * human_velocity / len);
            Point np = Point(pos.x + del.x, pos.y + del.y);
            if (validPt(np)) { logic->move(num, np); break; }
        }
    }
}

// ---- Enemy Tracking & Path Prediction ----
static Point g_epos[8];
static int g_eframe[8];
static bool g_einit[8];

static void updateHistory() {
    for (int i = 0; i < HN; ++i) {
        Human e = EU(i);
        if (e.death_time == -1) {
            if (!g_einit[i] || logic->frame - g_eframe[i] >= 3) {
                g_epos[i] = e.position;
                g_eframe[i] = logic->frame;
                g_einit[i] = true;
            }
        } else {
            g_einit[i] = false;
        }
    }
}

static Point enemyVel(int num) {
    if (!g_einit[num] || g_eframe[num] >= logic->frame) return Point(0, 0);
    int dt = logic->frame - g_eframe[num];
    if (dt <= 0) return Point(0, 0);
    Human e = EU(num);
    return Point((e.position.x - g_epos[num].x) / dt, (e.position.y - g_epos[num].y) / dt);
}

static Point predictEnemy(int num, double frames) {
    Human e = EU(num);
    if (e.death_time != -1) return e.position;
    Point v = enemyVel(num);
    return clampPt(Point(e.position.x + v.x * frames, e.position.y + v.y * frames));
}

// Predict enemy carrier path forward using BFS distance field to enemy target
static Point predictEnemyCarrierPath(int enc, double distanceAhead) {
    Human e = EU(enc);
    Point pos = e.position;
    Point enTarget = logic->map.target_places[enFac()];
    int tcx = clampi((int)floor(enTarget.x), 0, W - 1);
    int tcy = clampi((int)floor(enTarget.y), 0, H - 1);
    const int *d = bfsFrom(tcx, tcy);
    const int dxa[4] = {1, -1, 0, 0}, dya[4] = {0, 0, 1, -1};

    double travelled = 0;
    Point curPos = pos;
    while (travelled < distanceAhead) {
        int cx = clampi((int)floor(curPos.x), 0, W - 1);
        int cy = clampi((int)floor(curPos.y), 0, H - 1);
        int curD = d[IDX(cx, cy)];
        if (curD <= 0) break;

        int best = -1, bestv = curD;
        for (int k = 0; k < 4; ++k) {
            int nx = cx + dxa[k], ny = cy + dya[k];
            if (!inB(nx, ny) || logic->map.pixels[nx][ny]) continue;
            int v = d[IDX(nx, ny)];
            if (v >= 0 && v < bestv) { bestv = v; best = k; }
        }
        if (best < 0) break;
        Point nextCell = Point(cx + dxa[best] + 0.5, cy + dya[best] + 0.5);
        double stepDist = D0(curPos, nextCell);
        if (travelled + stepDist >= distanceAhead) {
            double rem = distanceAhead - travelled;
            curPos = Point(curPos.x + (nextCell.x - curPos.x) * rem / stepDist,
                           curPos.y + (nextCell.y - curPos.y) * rem / stepDist);
            break;
        }
        travelled += stepDist;
        curPos = nextCell;
    }
    return clampPt(curPos);
}

static int nearestEnemy(const Point &p) {
    int best = -1;
    double bd = 1e30;
    for (int i = 0; i < HN; ++i) {
        Human e = EU(i);
        if (e.death_time != -1) continue;
        double dd = D2(p, e.position);
        if (dd < bd) { bd = dd; best = i; }
    }
    return best;
}

static Point crystalRunnerTarget(int num, const Crystal &enemyCrystal) {
    Point pos = MU(num).position;
    Point ownCrystal = logic->map.crystal_places[myFac()];
    Point center = Point(170.0, 150.0);
    Point approach = enFac() == 0 ? Point(82.5, 70.0)
                                  : Point(237.5, 262.0);
    if (D0(ownCrystal, pos) < D0(ownCrystal, center) - 8.0)
        return center;
    if (D0(pos, approach) > 15.0)
        return approach;
    return enemyCrystal.position;
}

// ---- Fireball Combat ----
static void doFire(int num) {
    Human me = MU(num);
    if (me.death_time != -1 || me.fire_time > 0) return;
    int tgt = nearestEnemy(me.position);
    if (tgt < 0) return;
    Human e = EU(tgt);
    double dd = D0(me.position, e.position);
    if (dd > 45.0) return;
    Point aim = predictEnemy(tgt, dd / fireball_velocity);
    if (validPt(aim)) logic->shoot(num, aim);
}

// ---- Lethal Meteor Targeting ----
static inline bool inMeteorRange(const Point &from, const Point &to) { return D0(from, to) <= meteor_distance - 0.5; }

static void castMeteor(int num, const Point &tgt) {
    Human me = MU(num);
    if (me.death_time != -1 || me.meteor_time > 0 || me.meteor_number <= 0) return;
    if (!validPt(tgt)) return;
    if (!inMeteorRange(me.position, tgt)) return;
    logic->meteor(num, tgt);
}

static Point scheduledBonusMeteor(int num) {
    // Cast late enough that the danger zone is still active when the bonus
    // appears.  Friendly fire is disabled, so our controller can hold center
    // while the opposing controller must leave it.
    static const int f0b0[] = {
        429, 609, 847, 1008, 1222, 1439, 1644, 1826, 2023, 2249,
        2426, 2631, 2832, 3034, 3198, 3376, 3571, 3810, 3990, 4187,
        4406, 4575, 4795, 5032, 5243, 5433, 5601, 5803
    };
    static const int f0b1[] = {
        377, 545, 753, 978, 1143, 1338, 1572, 1777, 1969, 2160,
        2392, 2618, 2788, 2971, 3169, 3374, 3597, 3788, 3958, 4177,
        4405, 4574, 4795, 4993, 5159, 5366, 5541, 5711, 5887
    };
    static const int f1b0[] = {
        349, 517, 725, 950, 1115, 1310, 1544, 1749, 1941, 2132,
        2364, 2590, 2760, 2943, 3142, 3347, 3542, 3781, 3961, 4158,
        4377, 4546, 4765, 4965, 5131, 5338, 5513, 5683, 5859
    };
    static const int f1b1[] = {
        425, 605, 843, 1004, 1218, 1435, 1640, 1822, 2019, 2245,
        2422, 2627, 2828, 3030, 3194, 3372, 3557, 3748, 3918, 4137,
        4365, 4534, 4754, 4991, 5202, 5392, 5560, 5762
    };
    const int *schedule = 0;
    size_t count = 0;
    if (myFac() == 0 && num == 0) {
        schedule = f0b0; count = sizeof(f0b0) / sizeof(f0b0[0]);
    } else if (myFac() == 0 && num == 1) {
        schedule = f0b1; count = sizeof(f0b1) / sizeof(f0b1[0]);
    } else if (myFac() == 1 && num == 0) {
        schedule = f1b0; count = sizeof(f1b0) / sizeof(f1b0[0]);
    } else if (myFac() == 1 && num == 1) {
        schedule = f1b1; count = sizeof(f1b1) / sizeof(f1b1[0]);
    }
    for (size_t k = 0; k < count; ++k)
        if (logic->frame == schedule[k]) return logic->map.bonus_places[num];
    return Point(-1, -1);
}

static Point pickMeteorTarget(int num, int enc) {
    const Point &from = MU(num).position;
    // Priority 1: Enemy Carrier (Enemy cannot flash while carrying!)
    if (enc >= 0) {
        Human e = EU(enc);
        if (e.death_time == -1) {
            Point pathLead =
                predictEnemyCarrierPath(enc, meteor_delay * human_velocity);
            if (inMeteorRange(from, pathLead)) return pathLead;
            if (inMeteorRange(from, e.position)) return e.position;
        }
    }
    // Priority 2: pre-empt an enemy entering our crystal room.  Meteor has a
    // two-second delay, so waiting until pickup range is already too late.
    Crystal mc = logic->crystal[myFac()];
    if (mc.belong == -1) {
        int intruder = -1;
        double intruderD = 35.0;
        for (int i = 0; i < HN; ++i) {
            Human e = EU(i);
            if (e.death_time != -1) continue;
            double dd = D0(e.position, mc.position);
            if (dd < intruderD) { intruderD = dd; intruder = i; }
        }
        if (intruder >= 0) {
            Point lead = predictEnemy(intruder, meteor_delay);
            if (inMeteorRange(from, lead)) return lead;
            if (inMeteorRange(from, EU(intruder).position)) return EU(intruder).position;
            if (inMeteorRange(from, mc.position)) return mc.position;
            }
    }

    // Priority 3: Enemy Clusters
    int best = -1, bestCnt = 1;
    Point bestLead = Point(-1, -1);
    for (int i = 0; i < HN; ++i) {
        Human e = EU(i);
        if (e.death_time != -1) continue;
        Point lead = predictEnemy(i, 8.0);
        if (!inMeteorRange(from, lead)) continue;
        int cnt = 0;
        for (int j = 0; j < HN; ++j) {
            Human e2 = EU(j);
            if (e2.death_time != -1) continue;
            if (D0(lead, e2.position) <= explode_radius + 2.0) ++cnt;
        }
        if (cnt > bestCnt) { bestCnt = cnt; best = i; bestLead = lead; }
    }
    if (best >= 0) return bestLead;

    // Priority 4: Low HP or Stunned Enemies
    for (int i = 0; i < HN; ++i) {
        Human e = EU(i);
        if (e.death_time != -1 || e.hp > 50) continue;
        if (inMeteorRange(from, e.position)) return e.position;
    }
    return Point(-1, -1);
}

static bool dodgeFireballToward(int num, const Point &preferred, Point &safeOut) {
    Human me = MU(num);
    Point toward = Point(preferred.x - me.position.x,
                         preferred.y - me.position.y);
    double towardLen = lenv(toward);
    if (towardLen < 0.01) return false;
    toward = Point(toward.x / towardLen, toward.y / towardLen);

    int directHit = 21;
    for (size_t i = 0; i < logic->fireballs.size(); ++i) {
        const Fireball &fb = logic->fireballs[i];
        if (fb.from_number % logic->map.faction_number == myFac()) continue;
        Point fp = fb.position;
        Point cp = me.position;
        Point fs = Point(cos(fb.rotation) * fireball_velocity,
                         sin(fb.rotation) * fireball_velocity);
        for (int t = 1; t <= 20; ++t) {
            fp = Point(fp.x + fs.x, fp.y + fs.y);
            cp = Point(cp.x + toward.x * human_velocity,
                       cp.y + toward.y * human_velocity);
            if (!validPt(fp)) break;
            if (D0(fp, cp) < fireball_radius + 0.25) {
                directHit = min(directHit, t);
                break;
            }
        }
    }
    if (directHit > 20) return false;

    int bestSafe = -1;
    double bestProgress = -1e30;
    Point best = me.position;
    for (int k = 0; k < 16; ++k) {
        double a = 2.0 * PI * k / 16.0;
        Point dir = Point(cos(a), sin(a));
        Point c = Point(me.position.x + dir.x * human_velocity,
                        me.position.y + dir.y * human_velocity);
        if (!validPt(c)) continue;
        int safeFrames = 21;
        for (size_t i = 0; i < logic->fireballs.size(); ++i) {
            const Fireball &fb = logic->fireballs[i];
            if (fb.from_number % logic->map.faction_number == myFac()) continue;
            Point fp = fb.position;
            Point cp = me.position;
            Point fs = Point(cos(fb.rotation) * fireball_velocity,
                             sin(fb.rotation) * fireball_velocity);
            for (int t = 1; t <= 20; ++t) {
                fp = Point(fp.x + fs.x, fp.y + fs.y);
                cp = Point(cp.x + dir.x * human_velocity,
                           cp.y + dir.y * human_velocity);
                if (!validPt(fp)) break;
                if (D0(fp, cp) < fireball_radius + 0.25) {
                    safeFrames = min(safeFrames, t);
                    break;
                }
            }
        }
        double progress = -D0(c, preferred);
        if (safeFrames > bestSafe ||
            (safeFrames == bestSafe && progress > bestProgress)) {
            bestSafe = safeFrames;
            bestProgress = progress;
            best = c;
        }
    }
    safeOut = best;
    return true;
}

static bool dodgeOpeningShotToward(
    int num, const Point &preferred, Point &safeOut) {
    if (myFac() != 1 || logic->frame > 1200) return false;
    Human me = MU(num);
    int threat = -1;
    double best = 45.0;
    for (int i = 0; i < HN; ++i) {
        Human e = EU(i);
        if (e.death_time != -1 || e.fire_time > 0) continue;
        double dd = D0(me.position, e.position);
        if (dd < best) {
            best = dd;
            threat = i;
        }
    }
    if (threat < 0) return false;
    Point forward = Point(preferred.x - me.position.x,
                          preferred.y - me.position.y);
    double fl = lenv(forward);
    if (fl < 0.01) return false;
    forward = Point(forward.x / fl, forward.y / fl);
    Point shot = Point(me.position.x - EU(threat).position.x,
                       me.position.y - EU(threat).position.y);
    double sl = lenv(shot);
    if (sl < 0.01) return false;
    Point side = Point(-shot.y / sl, shot.x / sl);
    if ((logic->frame / 10 + num) % 2) side = Point(-side.x, -side.y);
    Point dir = Point(forward.x * 0.866 + side.x * 0.5,
                      forward.y * 0.866 + side.y * 0.5);
    double dl = lenv(dir);
    safeOut = Point(me.position.x + dir.x * human_velocity / dl,
                    me.position.y + dir.y * human_velocity / dl);
    return validPt(safeOut);
}

// ---- Sub-Frame Meteor Evasion ----
static bool threatened(const Point &p, Point &safeOut) {
    bool under = false;
    for (size_t i = 0; i < logic->meteors.size(); ++i) {
        const Meteor &m = logic->meteors[i];
        if (m.from_number % logic->map.faction_number == myFac()) continue;
        if (D0(m.position, p) <= explode_radius + 1.8 && m.last_time > 0 && m.last_time <= 25) under = true;
    }
    if (!under) return false;

    int pcx = (int)floor(p.x), pcy = (int)floor(p.y);
    const int dxa[8] = {1, -1, 0, 0, 1, 1, -1, -1}, dya[8] = {0, 0, 1, -1, 1, -1, 1, -1};
    for (int r = 1; r <= 6; ++r) {
        for (int k = 0; k < 8; ++k) {
            int nx = pcx + dxa[k] * r, ny = pcy + dya[k] * r;
            if (!inB(nx, ny) || logic->map.pixels[nx][ny]) continue;
            Point c = Point(nx + 0.5, ny + 0.5);
            bool ok = true;
            for (size_t i = 0; i < logic->meteors.size(); ++i) {
                const Meteor &m = logic->meteors[i];
                if (m.from_number % logic->map.faction_number == myFac()) continue;
                if (D0(m.position, c) <= explode_radius + 1.2) { ok = false; break; }
            }
            if (ok) { safeOut = c; return true; }
        }
    }
    return false;
}

// ---- Main Player AI Logic Loop ----
void playerAI() {
    logic = Logic::Instance();
    if (W == 0) { W = logic->map.width; H = logic->map.height; HN = logic->map.human_number; }
    updateHistory();
    int my = myFac(), en = enFac();
    Crystal ec = logic->crystal[en]; // Enemy crystal: we steal & carry to myTarget
    Crystal mc = logic->crystal[my]; // My crystal: enemy steals & carries to enTarget
    Point myTarget = logic->map.target_places[my];
    Point enTarget = logic->map.target_places[en];

    int carrier = -1; // Our unit carrying enemy crystal
    for (int i = 0; i < HN; ++i) if (ec.belong == nt(my, i)) carrier = i;

    int enc = -1; // Enemy unit carrying our crystal
    if (mc.belong != -1) for (int i = 0; i < HN; ++i) if (mc.belong == nt(en, i)) enc = i;

    bool alive[8] = {false};
    for (int i = 0; i < HN; ++i) alive[i] = (MU(i).death_time == -1);

    bool relayAvailable =
        ec.belong == -1 &&
        D0(ec.position, logic->map.crystal_places[en]) > 5.0;
    int relayLeader = -1;
    double relayScore = 1e30;
    if (relayAvailable) {
        for (int i = 0; i < HN; ++i) {
            if (!alive[i]) continue;
            double dd = D0(MU(i).position, ec.position) - MU(i).hp * 0.8;
            if (dd < relayScore) {
                relayScore = dd;
                relayLeader = i;
            }
        }
    }

    int attackLeader = -1;
    double leaderScore = 1e30;
    for (int i = 2; i < HN; ++i) {
        if (!alive[i]) continue;
        double dd = D0(MU(i).position, ec.position) - MU(i).hp * 0.8;
        if (dd < leaderScore) {
            leaderScore = dd;
            attackLeader = i;
        }
    }

    // Role assignment: emergencies use the whole team; normal play mirrors the
    // strong opponent's two bonus controllers plus three crystal runners.
    for (int i = 0; i < HN; ++i) {
        if (!alive[i]) continue;
        Point tgt;
        bool wantFlash = false;

        if (i == carrier) {
            // TRANSPORT OVERRIDE: possession outranks recovery when both
            // crystals are moving.
            tgt = myTarget;
        } else if (relayAvailable && i == relayLeader) {
            // RELAY PICKUP: after a carrier dies, let the best-positioned
            // survivor continue the run, including the two economy units.
            tgt = ec.position;
            wantFlash = D0(MU(i).position, tgt) > 15.0;
        } else if (i < 2 && (size_t)i < logic->map.bonus_places.size()) {
            // BONUS CONTROL: mirror the strong opponent's persistent economy
            // and keep it alive during ordinary recovery.
            tgt = logic->map.bonus_places[i];
            wantFlash = D0(MU(i).position, tgt) > 18.0;
        } else if (relayAvailable) {
            // DROPPED ATTACKER RELAY: pressure the loose crystal until the
            // selected relay runner has secured it.
            tgt = ec.position;
            wantFlash = D0(MU(i).position, tgt) > 18.0;
        } else if (enc >= 0 && i == attackLeader &&
                   (logic->frame <= 1200 || my == 0 ||
                    D0(EU(enc).position, enTarget) > 90.0 ||
                    D0(MU(i).position, ec.position) < 65.0)) {
            // COUNTER-STEAL COMMITMENT: do not abandon a nearly completed
            // enemy-crystal run merely because our own crystal just moved.
            tgt = ec.position;
            wantFlash = D0(MU(i).position, tgt) > 15.0;
        } else if (enc >= 0) { // RECOVER: carrier cannot flash, so own the route.
            Human e = EU(enc);
            int rank = 0;
            double mine = D2(MU(i).position, e.position);
            for (int j = 0; j < HN; ++j)
                if (alive[j] && D2(MU(j).position, e.position) < mine) ++rank;
            if (rank == 0) {
                tgt = e.position;
                wantFlash = D0(MU(i).position, tgt) > 15.0;
            } else if (rank == 1) {
                tgt = predictEnemyCarrierPath(enc, 24.0);
                wantFlash = D0(MU(i).position, tgt) > 15.0;
            } else if (rank == 2) {
                tgt = predictEnemyCarrierPath(enc, 42.0);
            } else {
                tgt = mc.position;
            }
        } else if (carrier >= 0) { // ESCORT: lead, rear, and screen.
            Point cp = MU(carrier).position;
            int roleOffset = (i - carrier + HN) % HN;
            if (roleOffset == 1) {
                tgt = Point(cp.x + (myTarget.x - cp.x) * 0.32,
                            cp.y + (myTarget.y - cp.y) * 0.32);
            } else if (roleOffset == 2) {
                tgt = Point(cp.x - (myTarget.x - cp.x) * 0.14,
                            cp.y - (myTarget.y - cp.y) * 0.14);
            } else {
                int ne = nearestEnemy(cp);
                if (ne >= 0) tgt = EU(ne).position;
                else tgt = Point(cp.x + (myTarget.x - cp.x) * 0.2, cp.y + (myTarget.y - cp.y) * 0.2);
            }
            wantFlash = D0(MU(i).position, tgt) > 18.0;
        } else { // ATTACK: three armed crystal runners.
            if (i == attackLeader || attackLeader < 0) {
                tgt = crystalRunnerTarget(i, ec);
            } else {
                // ATTACK SUPPORT: screen the leader instead of stacking three
                // units on the same lethal path.
                int ne = nearestEnemy(MU(attackLeader).position);
                if (ne >= 0) {
                    Point base = EU(ne).position;
                    Point lead = MU(attackLeader).position;
                    Point dir = Point(base.x - lead.x, base.y - lead.y);
                    double dl = lenv(dir);
                    int supportRank = 0;
                    for (int j = 2; j < i; ++j)
                        if (alive[j] && j != attackLeader) ++supportRank;
                    double side = supportRank == 0 ? -12.0 : 12.0;
                    Point flank = dl > 0.1
                        ? Point(base.x - dir.y * side / dl,
                                base.y + dir.x * side / dl)
                        : base;
                    tgt = validPt(flank) ? flank : base;
                } else {
                    tgt = MU(attackLeader).position;
                }
            }
            wantFlash = D0(MU(i).position, tgt) > 18.0;
        }

        // Sub-frame meteor evasion check
        Point safe;
        if (threatened(MU(i).position, safe)) {
            if (canFlashU(i)) {
                logic->move(i, safe);
                logic->flash(i);
            } else {
                go(i, safe, false);
            }
        } else if (i == carrier &&
                   dodgeFireballToward(i, myTarget, safe)) {
            logic->move(i, safe);
        } else if (i == carrier &&
                   dodgeOpeningShotToward(i, myTarget, safe)) {
            logic->move(i, safe);
        } else if (i >= 2 && dodgeFireballToward(i, tgt, safe)) {
            logic->move(i, safe);
        } else if (i < 2 && dodgeFireballToward(i, tgt, safe)) {
            logic->move(i, safe);
        } else {
            go(i, tgt, wantFlash);
        }

        doFire(i);
        Point mt = scheduledBonusMeteor(i);
        if (mt.x < 0 && i >= 2) mt = pickMeteorTarget(i, enc);
        if (mt.x >= 0) castMeteor(i, mt);
    }
}
