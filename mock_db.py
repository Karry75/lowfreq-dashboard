"""
Mock DB：模拟 MySQL cursor。
- 23693 个活跃协议（1359 欠租 + 16534 低频候选 + 5800 其他）
- cb_battery_circulate_log 完全空（模拟用户环境）
- cb_exchange_order.battery_device_sn 为空（SN 取不到）
- v10.28.44 扩展：cb_admin / cb_reception_log 注入样本，用于验证多选 + 员工 ID 映射 + 退订归类
"""
import datetime

class MockCursor:
    def __init__(self, db):
        self.db = db
        self.sql = ''
        self.params = None
        self._rows = None

    def execute(self, sql, params=None):
        self.sql = sql.strip().lower()
        self.params = params
        self._rows = None
        s = self.sql

        # 表结构探测
        if 'show columns from cb_battery' in s and 'battery' in s and 'bind_log' not in s:
            self._rows = [('id',),('device_sn',),('power',),('voltage_in',),('current_in',),('using',),('is_del',),('last_location_address',),('last_location_time',)]
        elif 'show columns from cb_bike_battery_bind_log' in s:
            self._rows = [('id',),('battery_id',),('bike_id',),('is_del',),('update_time',)]
        elif 'show columns from cb_reception_log' in s:
            self._rows = [('id',),('agreement_id',),('solver_user_name',),('detail',),('type',),('create_time',),('consumer_user_id',),('is_del',)]
        elif 'show columns from cb_battery_circulate_log' in s:
            self._rows = [('id',),('battery_device_sn',),('create_time',),('outflow_name',),('inflow_name',),('business_type_second',),('is_del',)]
        elif 'show columns from cb_exchange_order' in s:
            self._rows = [('id',),('exchange_agreement_id',),('battery_device_sn',),('create_time',),('business_type_second',),('status',),('is_del',),('back_battery_time',)]
        elif 'show columns from cb_exchange_agreement' in s:
            self._rows = [('id',),('user_id',),('status',),('is_del',),('product_id',),('product_name',),('deposit_fee',),('deposit_status',),('deposit_payway',),('pkg_name',),('sys_city_name',),('province',),('city',),('area',),('street',),('community',),('rent_expire_time',),('activation_time',),('type',),('agent',),('use_days',)]
        elif 'show columns from cb_user' in s:
            self._rows = [('id',),('phone',),('mobile',),('is_del',),('nickname',)]
        elif 'show columns from cb_admin' in s:
            self._rows = [('id',),('name',),('is_del',)]  # v10.28.44：员工表
        elif 'show columns from cb_staff' in s:
            self._rows = [('id',),('name',),('is_del',)]  # v10.28.44：员工表 fallback

        # 抽样探测
        elif 'count(*) c from (select 1 from cb_user' in s:
            self._rows = [(100000,)]
        elif 'count(*) c from (select 1 from cb_battery ' in s or 'count(*) c from (select 1 from cb_battery)' in s:
            self._rows = [(8000,)]
        elif 'count(*) c from (select 1 from cb_bike_battery_bind_log' in s:
            self._rows = [(12000,)]
        elif 'count(*) c from (select 1 from cb_reception_log' in s:
            self._rows = [(150000,)]
        elif 'count(*) c from (select 1 from cb_exchange_agreement' in s:
            self._rows = [(160000,)]
        elif 'count(*) c from (select 1 from cb_exchange_order' in s:
            self._rows = [(3000000,)]
        elif 'count(*) c from (select 1 from cb_battery_circulate_log' in s:
            self._rows = [(0,)]  # 流通表空
        elif 'is not null' in s and 'cb_user' in s and 'phone' in s:
            self._rows = [(99418,)]
        elif 'is not null' in s and 'cb_reception_log' in s:
            self._rows = [(150000,)]

        # 主查询
        elif 'max(back_battery_time)' in s or 'max( back_battery_time)' in s:
            self._rows = [(int(datetime.datetime(2026,8,28,10,0,0).timestamp()),)]
        elif 'from cb_exchange_agreement' in s and 'status in' in s and 'is_del' in s:
            self._rows = self.db.agreements
        elif 'count' in s and 'min(back_battery_time)' in s and 'group by exchange_agreement_id' in s:
            # aid_swap_times: COUNT/MIN/MAX
            rows = []
            for aid in self.db.agreement_ids:
                rows.append({'aid': aid, 'c': 3, 'mn': 1760000000, 'mx': 1787000000})
            self._rows = rows
        elif 'from cb_battery_circulate_log' in s:
            self._rows = []
        elif 'from cb_exchange_order o' in s and 'exchange_agreement_id' in s:
            # aid_last_order: 每个 aid 一条，SN 为空
            rows = []
            for aid in self.db.agreement_ids[:50000]:
                rows.append({'aid': aid, 'battery_device_sn': '', 'create_time': datetime.datetime(2026,7,15,10,0,0), 'business_type_second': 'back_battery', 'status': 'completed'})
            self._rows = rows
        elif 'from cb_exchange_order' in s and 'order by' in s and 'limit' in s:
            # aid_orders 分批
            aids = self.params[0] if self.params and isinstance(self.params, (list, tuple)) else []
            rows = []
            for aid in aids:
                rows.append({'aid': aid, 'battery_device_sn': '', 'create_time': datetime.datetime(2026,7,15,10,0,0), 'business_type_second': 'back_battery'})
            self._rows = rows
        elif 'from cb_reception_log' in s:
            # v10.28.44：注入样本接待记录
            use_aids = []
            if self.params:
                if isinstance(self.params, (list, tuple)):
                    p0 = self.params[0]
                    if isinstance(p0, list):
                        use_aids = p0
                    elif isinstance(p0, int):
                        use_aids = self.params if all(isinstance(x, int) for x in self.params) else []
                    elif isinstance(p0, tuple):
                        use_aids = list(p0) if all(isinstance(x, int) for x in p0) else []
            # 拆分：去掉子查询里的 group by，仅看外层 SELECT 后是否有 group by
            main_part = s.split(' join ')[0] if ' join ' in s else s
            has_groupby_main = ' group by ' in main_part
            if has_groupby_main and (' as _t' in main_part or ' as _typ' in main_part) and 'count(*)' in main_part:
                # SELECT _slv AS _s, _typ AS _t, COUNT(*) c GROUP BY _slv, _typ
                rows = [{'_s': str(i), 'c': 10, '_t': 'followup'} for i in range(20)]
                self._rows = rows
            elif has_groupby_main:
                # SELECT _slv AS _s, COUNT(*) c, COUNT(DISTINCT _uid) uc GROUP BY _slv
                rows = [{'_s': str(i), 'c': 10, 'uc': 8} for i in range(20)]
                self._rows = rows
            else:
                # 明细查询（含 JOIN 子查询也算明细）
                rows = []
                for i, aid in enumerate(use_aids[:200]):
                    rows.append({
                        '_agr': aid,
                        '_uid': aid,
                        '_typ': 'followup',
                        '_slv': str(i % 20),
                        '_det': '用户答应明天去换电',
                        '_ct': int(datetime.datetime(2026, 8, max(1, 28 - (i % 27)), 10, 0, 0).timestamp() * 1000)
                    })
                self._rows = rows
        elif 'from cb_admin' in s or 'from `cb_admin`' in s:
            if 'show columns from' in s:
                self._rows = [('id',),('name',),('is_del',)]
            elif '`name`' in s:
                # v10.28.44：返回员工 ID → 姓名 映射
                names = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十',
                         '陈掌柜', '运营-王一', '王转前管理员', '刘建华', '黄師傅', '李晓静',
                         '鲍工权', '娜哪娜工', '王一地运维经理', '阮香格', '娜哪娜经理', '廖志成']
                rows = [{'_id': i, '_nm': names[i]} for i in range(20)]
                self._rows = rows
            else:
                rows = [{'id': i} for i in range(20)]
                self._rows = rows
        elif 'from cb_staff' in s or 'from `cb_staff`' in s:
            names = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十',
                     '陈掌柜', '运营-王一', '王转前管理员', '刘建华', '黄師傅', '李晓静',
                     '鲍工权', '娜哪娜工', '王一地运维经理', '阮香格', '娜哪娜经理', '廖志成']
            rows = [{'_id': i, '_nm': names[i]} for i in range(20)]
            self._rows = rows
        elif 'from cb_user' in s:
            rows = []
            for aid in self.db.agreement_ids[:50000]:
                rows.append({'id': aid, 'phone': f'138{aid:08d}', 'mobile': '', 'is_del': 0})
            self._rows = rows
        elif 'from cb_battery_status' in s and 'battery_id' in s:
            # v10.28.30 验证用：故意留空，逼出「cb_battery 自带电气字段」的兜底路径
            self._rows = []
        elif 'from cb_bike_battery_bind_log' in s:
            # 必须返回 user_id，否则 bind_map[r['user_id']] 抛 KeyError → 整段被 except 吞掉
            rows = []
            for uid in range(1, 23694):
                rows.append({'user_id': uid, 'battery_id': f'BAT{(uid % 6000) + 1:06d}'})
            self._rows = rows
        elif 'from cb_battery where' in s and 'device_sn' in s:
            # 通用：按 SQL 实际 SELECT 的列回显，避免"查询被拦截但缺列"造成假阴性
            import re as _re
            _m = _re.search(r'select\s+(.*?)\s+from', s, _re.S)
            _cols = [c.strip().strip('`') for c in _m.group(1).split(',')] if _m else ['id']
            _vals = {'id': 'BAT000001', 'device_sn': 'BAT000001',
                     'online_status': 'online', 'power': 62,
                     'voltage_in': 48.6, 'current_in': 2.1,
                     'last_location_address': '深圳市福田区华强北换电柜A03',
                     'last_location_time': datetime.datetime(2026, 8, 26, 9, 30, 0)}
            rows = []
            for i in range(1, 6001):
                row = {}
                for c in _cols:
                    if c == 'id':
                        row[c] = f'BAT{i:06d}'
                    elif c == 'device_sn':
                        row[c] = f'BAT{i:06d}'
                    elif c == 'online_status':
                        row[c] = 'online' if i % 3 else 'offline'
                    elif c == 'power':
                        row[c] = 40 + i % 55
                    elif c == 'voltage_in':
                        row[c] = round(48.0 + (i % 12) * 0.1, 2)
                    elif c == 'current_in':
                        row[c] = round(1.0 + (i % 20) * 0.1, 2)
                    else:
                        row[c] = _vals.get(c, '')
                rows.append(row)
            self._rows = rows
        elif 'from cb_battery_status bs' in s and 'join cb_battery b' in s:
            # 电池状态关联
            rows = []
            for i in range(1, 6001):
                rows.append({'battery_id': f'BAT{i:06d}', 'soc': 50+i%30, 'vol': 60.0+i%5, 'cur': 1.5, 'using': 'charging', 'lrt_ms': 1787000000000+i*1000, 'last_location_address': '深圳市福田区华强北换电柜', 'last_location_time': '2026-08-25 10:00:00'})
            self._rows = rows
        elif 'from cb_battery b' in s and 'device_sn' in s:
            rows = []
            for i in range(1, 6001):
                rows.append({'id': f'BAT{i:06d}', 'device_sn': f'BAT{i:06d}', 'is_del': 0})
            self._rows = rows
        elif 'select id' in s and 'cb_battery' in s and 'is_del' in s:
            rows = []
            for i in range(1, 6001):
                rows.append({'id': f'BAT{i:06d}'})
            self._rows = rows
        else:
            self._rows = []

    def fetchall(self):
        if self._rows is None: return []
        return self._rows

    def fetchone(self):
        rs = self.fetchall()
        if not rs: return None
        first = rs[0]
        if isinstance(first, dict): return first
        # tuple → dict，列名取自 SQL 中 "SELECT ... FROM" 之间第一个 AS 后的别名，没有就用 'c0','c1'...
        import re
        m = re.search(r'select\s+(.*?)\s+from', self.sql, re.S)
        cols = ['c0']
        if m:
            parts = [p.strip() for p in m.group(1).split(',')]
            cols = [p.split(' as ')[-1].strip().split()[-1].strip('`') for p in parts]
        return dict(zip(cols, first))

class MockConn:
    def __init__(self):
        self.db = MockDB()
    def cursor(self):
        return MockCursor(self.db)
    def commit(self): pass
    def close(self): pass

class MockDB:
    def __init__(self):
        self.agreement_ids = list(range(1, 23694))
        self.agreements = []
        # v10.28.44：扩展协议状态分布以验证退订归类
        #   - 1~1359：owe_rent（欠租）
        #   - 1360~3000：unsubscribing（退订中）—— 应归 S10
        #   - 3001~3200：terminated（已退订）—— 应归 S7
        #   - 3201+：working（生效中）
        for aid in self.agreement_ids:
            if aid <= 1359:
                _status = 'owe_rent'
            elif aid <= 3000:
                _status = 'unsubscribing'
            elif aid <= 3200:
                _status = 'terminated'
            else:
                _status = 'working'
            is_owe = 1 if _status == 'owe_rent' else 0
            is_lf_zone = 1359 < aid <= 1359 + 16534
            self.agreements.append({
                'id': aid,
                'user_id': aid,
                'status': _status,
                'is_del': 0,
                'product_id': 'PRD-001',
                'product_name': '深圳4824' if aid%3==0 else ('杭州4824' if aid%3==1 else '葫芦4814'),
                'deposit_fee': 9900,
                'deposit_status': 'on',
                'deposit_payway': 'wechat',
                'pkg_name': '月套餐',
                'sys_city_name': '深圳市' if aid%3==0 else ('杭州市' if aid%3==1 else '葫芦岛市'),
                'province': '广东省' if aid%3==0 else ('浙江省' if aid%3==1 else '辽宁省'),
                'city': '深圳' if aid%3==0 else ('杭州' if aid%3==1 else '葫芦岛'),
                'area': '福田区' if aid%3==0 else ('西湖区' if aid%3==1 else '龙港区'),
                'street': '华强北街道' if aid%3==0 else ('文一路街道' if aid%3==1 else '龙港街道'),
                'community': '华强北社区' if aid%3==0 else ('文一社区' if aid%3==1 else '龙港社区'),
                'rent_expire_time': datetime.datetime(2026,9,1),
                'activation_time': datetime.datetime(2026,1,15),
                'type': 'single',
                'agent': '深圳直营',
                'use_days': 195, 'user_phone': f'139{aid:08d}', 'user_name': f'用户{aid}', 'battery_product_id': 'BAT-P-001',
            })
