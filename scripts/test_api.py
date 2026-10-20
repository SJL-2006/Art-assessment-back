"""运行时接口测试脚本 —— 验证 A 模块核心链路能跑通。

启动：先 `python manage.py runserver 8000`，再：
    python scripts/test_api.py
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0


def _unwrap(body):
    """从信封 {code, message, data} 中取出业务数据。"""
    if isinstance(body, dict) and "data" in body and "code" in body:
        return body["data"]
    return body


def _token(body):
    """取 access token。"""
    data = _unwrap(body)
    if isinstance(data, dict):
        return data.get("access")
    return None


def req(method, path, data=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=5)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, str(e)


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}  -- {detail}")


# ============================================================
print("=== 1. 登录（省级管理员） ===")
status, body = req("POST", "/api/auth/login/", {"username": "admin_province", "password": "123456"})
check("200", status == 200, f"status={status}")
token_province = _token(body)
check("拿到 access token", bool(token_province))

print("\n=== 2. GET /api/users/me/ ===")
status, body = req("GET", "/api/users/me/", token=token_province)
me = _unwrap(body)
check("200", status == 200, f"status={status}, body={body}")
check("role=province", me.get("role") == "province" if isinstance(me, dict) else False)

print("\n=== 3. PUT /api/users/me/ 修改真实姓名 ===")
status, body = req("PUT", "/api/users/me/", {"real_name": "省管理员改后"}, token=token_province)
check("200", status == 200, f"status={status}")

print("\n=== 4. POST /api/users/change-password/ (改回 123456) ===")
_, body2 = req("POST", "/api/users/change-password/", {"old_password": "123456", "new_password": "NewPass123"}, token=token_province)
check("200", _unwrap(body2) is not None or body2.get("code") == 0, f"body={body2}")
_, _ = req("POST", "/api/users/change-password/", {"old_password": "NewPass123", "new_password": "123456"}, token=token_province)

print("\n=== 5. GET /api/org/regions/ (省级查所有) ===")
status, body = req("GET", "/api/org/regions/", token=token_province)
regions = _unwrap(body)
check("200", status == 200, f"status={status}")
check("有 3 个行政区", regions.get("total") == 3 if isinstance(regions, dict) else False, f"regions={regions}")

print("\n=== 6. GET /api/org/schools/ ===")
status, body = req("GET", "/api/org/schools/", token=token_province)
schools = _unwrap(body)
check("200", status == 200)
check("有 1 个学校", schools.get("total") == 1 if isinstance(schools, dict) else False)
school_id = schools.get("list", [{}])[0].get("id") if isinstance(schools, dict) else None

print("\n=== 7. 创建班级 POST /api/classroom/classes/ (教师) ===")
_, t_body = req("POST", "/api/auth/login/", {"username": "teacher01", "password": "123456"})
t_token = _token(t_body)
# 先查一下有没有已存在的班级（防止重复跑撞唯一约束）
_, cls_list_body = req("GET", "/api/classroom/classes/", token=t_token)
cls_list = _unwrap(cls_list_body)
existing_id = None
if isinstance(cls_list, dict):
    existing_id = cls_list.get("list", [{}])[0].get("id") if cls_list.get("total", 0) > 0 else None

if existing_id:
    class_id = existing_id
    check(f"已有班级 id={class_id}", True)
else:
    status, body = req("POST", "/api/classroom/classes/", {
        "name": "五年级1班",
        "code": "C2024001",
        "grade": "五年级",
        "school": school_id,
    }, token=t_token)
    class_data = _unwrap(body)
    check("201 创建成功", status == 201, f"status={status}, body={body}")
    class_id = class_data.get("id") if isinstance(class_data, dict) else None
    check("返回 class_id", bool(class_id), f"body={body}")

print("\n=== 8. GET /api/classroom/classes/ (教师列表) ===")
status, body = req("GET", "/api/classroom/classes/", token=t_token)
cs = _unwrap(body)
check("200", status == 200)
check("至少 1 个班级", cs.get("total", 0) >= 1 if isinstance(cs, dict) else False)

print("\n=== 9. POST /api/classroom/classes/{id}/join/ (学生申请加入) ===")
_, s_body = req("POST", "/api/auth/login/", {"username": "student01", "password": "123456"})
s_token = _token(s_body)
status, body = req("POST", f"/api/classroom/classes/{class_id}/join/", {}, token=s_token)
check("201 申请提交", status == 201, f"status={status}, body={body}")

print("\n=== 10. POST .../approve/ (教师审核学生申请) ===")
# 查一下学生的 id（用 teacher token 查账号列表里 student01）
_, sc_body = req("POST", "/api/auth/login/", {"username": "admin_school", "password": "123456"})
sc_token = _token(sc_body)
_, users_body = req("GET", "/api/accounts/?role=student", token=sc_token)
users_data = _unwrap(users_body)
student_id = None
if isinstance(users_data, dict):
    for u in users_data.get("list", []):
        if u.get("username") == "student01":
            student_id = u["id"]
check("找到 student_id", student_id is not None, f"users={users_data}")

if student_id:
    status, body = req("POST", f"/api/classroom/classes/{class_id}/students/{student_id}/approve/", {"approved": True}, token=t_token)
    check("200 审核通过", status == 200, f"status={status}, body={body}")

print("\n=== 11. GET /api/accounts/ (学校管理员查账号 scope 收敛) ===")
status, body = req("GET", "/api/accounts/", token=sc_token)
accs = _unwrap(body)
check("200", status == 200, f"status={status}")
if isinstance(accs, dict):
    items = accs.get("list", [])
    check("scope 收敛到本校 (≤4 人)", len(items) <= 4, f"items={[i.get('username') for i in items]}")

print("\n=== 12. POST /api/accounts/ (创建学生账号) ===")
status, body = req("POST", "/api/accounts/", {
    "username": "student02", "password": "Test1234", "role": "student",
    "real_name": "赵小红", "student_no": "S2024002", "school": school_id,
}, token=sc_token)
check("201 创建成功", status == 201, f"status={status}, body={body}")

print("\n=== 13. GET /api/logs/ (省级查日志) ===")
status, body = req("GET", "/api/logs/", token=token_province)
check("200", status == 200, f"status={status}")

print("\n=== 14. 学生查账号列表被拦截 (403) ===")
status, _ = req("GET", "/api/accounts/", token=s_token)
check("403/401 被拦截", status in (401, 403), f"status={status}")

print("\n=== 15. POST /api/accounts/batch-create/ ===")
status, body = req("POST", "/api/accounts/batch-create/", {
    "role": "teacher", "prefix": "TNEW", "count": 3, "default_password": "123456", "school": school_id,
}, token=sc_token)
batch_data = _unwrap(body)
check("200", status == 200, f"status={status}, body={body}")
if isinstance(batch_data, dict):
    check("created=3", batch_data.get("created") == 3, f"data={batch_data}")

print("\n=== 16. POST /api/accounts/{id}/reset-password/ ===")
if student_id:
    status, body = req("POST", f"/api/accounts/{student_id}/reset-password/", {}, token=sc_token)
    check("200", status == 200, f"status={status}")

print("\n" + "=" * 50)
print(f"结果：✅ {PASS} 通过 / ❌ {FAIL} 失败 / 共 {PASS + FAIL}")
sys.exit(0 if FAIL == 0 else 1)
