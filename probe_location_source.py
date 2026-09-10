"""
定位数据源探测 v1
- 目的：回访排班新增「车辆最后定位地址」列，需先确认数据来源
- 优先级：cb_battery_circulate_log 已存字段 > cb_battery 关联 > 独立 GPS/车辆表
- 用法：python3 probe_location_source.py （需在 lowfreq_local/ 下，读取 db_conf.json）
- 输出：控制台打印 + probe_location_source.json
"""
import os, sys, json, pymysql, time

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "db_conf.json")
OUT  = os.path.join(HERE, "probe_location_source.json")

def conn():
    c = json.load(open(CONF, encoding="utf-8"))
    for i in range(3):
        try:
            return pymysql.connect(
                host=c["host"], port=c.get("port", 3306),
                user=c["user"], password=c["password"],
                database=c["database"], charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=20, read_timeout=120, write_timeout=60,
            )
        except Exception as e:
            print(f"[retry {i+1}] connect fail:", e); time.sleep(2)
    raise SystemExit("DB unreachable")

def list_tables(cur):
    cur.execute("SHOW TABLES")
    return [list(r.values())[0] for r in cur.fetchall()]

def get_cols(cur, table):
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    return [(r["Field"], str(r["Type"])[:30]) for r in cur.fetchall()]

def main():
    c = conn(); cur = c.cursor()
    print("=== 1. 候选表扫描（关键词：gps/vehicle/car/addr/location/position/lng/lat） ===")
    candidates = []
    for t in list_tables(cur):
        low = t.lower()
        if any(k in low for k in ["gps","vehicle","car","addr","location","position","lng","lat","trace","track","轨迹","定位","地址","车辆","电池"]):
            cols = get_cols(cur, t)
            candidates.append({"table": t, "cols": cols})
            print(f" - {t}  ({len(cols)} cols)")
            for f, ty in cols:
                print(f"     · {f:<35} {ty}")
    print()
    print("=== 2. 流通表字段补全（cb_battery_circulate_log 当前没拉的列） ===")
    cur.execute("SHOW COLUMNS FROM cb_battery_circulate_log")
    cur_cols = {r["Field"] for r in cur.fetchall()}
    print(" 现有已 SELECT:", "battery_device_sn, create_time, outflow_name, inflow_name, business_type_second")
    interesting = [c for c in sorted(cur_cols)
                   if any(k in c.lower() for k in ["addr","address","loc","gps","lng","lat","province","city","district","street","pos","coord","area","region","site","station","cab"])]
    print(" 可疑字段（流通表里）:")
    for c in interesting:
        print("  -", c)
    # 试取一行流通表完整行（看 addr/lng/lat 等是否真的有值）
    cur.execute("SELECT * FROM cb_battery_circulate_log WHERE is_del=0 ORDER BY create_time DESC LIMIT 1")
    sample = cur.fetchone() or {}
    print("  最新一条流通记录字段(已脱敏):")
    for k, v in sample.items():
        sv = (str(v) if v is not None else "")
        if any(x in k.lower() for x in ["addr","address","loc","gps","lng","lat","province","city","district","street","pos","coord","area","region","site","station","cab"]):
            print(f"    ★ {k} = {sv[:80]}")
    print()
    print("=== 3. cb_battery 表字段（看电池是否有自带的定位） ===")
    cur.execute("SHOW COLUMNS FROM cb_battery")
    bat_cols = [(r["Field"], str(r["Type"])[:30]) for r in cur.fetchall()]
    for f, ty in bat_cols:
        flag = "  ★" if any(k in f.lower() for k in ["addr","gps","lng","lat","loc","pos","coord","province","city","district","street"]) else "   "
        print(f" {flag} {f:<35} {ty}")
    print()
    print("=== 4. 样例：1 条协议的最近车辆定位（如果有） ===")
    cur.execute("""
        SELECT a.id agreement_id, a.user_id, a.user_phone
        FROM cb_exchange_agreement a
        WHERE a.is_del=0 AND a.status IN ('working','owe_rent','unsubscribing')
        LIMIT 1
    """)
    a = cur.fetchone()
    if a:
        print(f" 协议ID={a['agreement_id']} user_id={a['user_id']} phone={a['user_phone']}")
        # 找该协议关联的电池 SN
        cur.execute("SELECT battery_device_sn FROM cb_exchange_order WHERE exchange_agreement_id=%s AND is_del=0 ORDER BY id DESC LIMIT 1", (a["agreement_id"],))
        sn_row = cur.fetchone()
        sn = sn_row["battery_device_sn"] if sn_row else None
        print(f" 最近订单电池SN: {sn}")
        if sn:
            for t in [c["table"] for c in candidates if "gps" in c["table"].lower() or "vehicle" in c["table"].lower() or "vehicle" in t.lower() or "car" in t.lower() or "addr" in c["table"].lower()]:
                try:
                    # 猜关联列名
                    for col_guess in ["battery_device_sn","battery_sn","sn","device_sn"]:
                        cols = [f for f,_ in next(cc for cc in candidates if cc["table"]==t)["cols"]]
                        if col_guess in cols:
                            cur.execute(f"SELECT * FROM `{t}` WHERE `{col_guess}`=%s ORDER BY id DESC LIMIT 1", (sn,))
                            r = cur.fetchone()
                            if r:
                                print(f"  候选表 {t}.{col_guess}={sn} → 行存在")
                                for k,v in r.items():
                                    print(f"     · {k} = {str(v)[:80]}")
                            break
                except Exception as e:
                    print(f"  {t} 探测异常: {e}")
    # 写 JSON
    json.dump({
        "candidates": candidates,
        "cur_interesting_cols": interesting,
        "battery_cols": bat_cols,
    }, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    print()
    print(f"=== 完整结果已写入: {OUT} ===")
    c.close()

if __name__ == "__main__":
    main()
