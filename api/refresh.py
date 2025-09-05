# api/refresh.py
import os, json, requests
from flask import Flask, request, make_response

app = Flask(__name__)

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
REDIS_KEY = "kstartup:announcements:v1"
DATABASE_URL = os.environ.get("DATABASE_URL")  # postgresql://...

def _set_redis(val: str, ex: int = 3600) -> bool:
    r = requests.get(
        f"{REDIS_URL}/set/{REDIS_KEY}/{requests.utils.quote(val, safe='')}",
        params={"ex": ex},
        headers={"Authorization": f"Bearer {REDIS_TOKEN}"},
        timeout=10,
    )
    return r.ok

def fetch_from_db():
    # psycopg는 DATABASE_URL 있을 때만 import (서버리스 이미지 경량화)
    import psycopg
    rows = []
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select pbanc_sn, biz_pbanc_nm, intg_pbanc_biz_nm, pbanc_ctnt,
                       supt_biz_clsfc, aply_trgt, aply_trgt_ctnt, supt_regin,
                       to_char(pbanc_rcpt_bgng_dt,'YYYYMMDD') as pbanc_rcpt_bgng_dt,
                       to_char(pbanc_rcpt_end_dt,'YYYYMMDD') as pbanc_rcpt_end_dt,
                       pbanc_ntrp_nm, sprv_inst, biz_prch_dprt_nm, biz_gdnc_url,
                       detl_pg_url, aply_mthd_onli_rcpt_istc, prch_cnpl_no,
                       rcrt_prgs_yn, biz_enyy, biz_trgt_age
                from public.kstartup_announcements
                order by rcrt_prgs_yn desc, pbanc_rcpt_end_dt desc
                limit 600
            """)
            cols = [d[0] for d in cur.description]
            for r in cur.fetchall():
                rows.append(dict(zip(cols, r)))
    return rows

@app.route("/", methods=["POST", "GET", "OPTIONS"])
def refresh():
    # CORS
    resp = make_response()
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if request.method == "OPTIONS":
        resp.status_code = 204
        return resp

    if not (REDIS_URL and REDIS_TOKEN):
        resp.set_data("Missing Upstash env")
        resp.status_code = 500
        return resp

    # 1) DB 우선 (DATABASE_URL 있을 때)
    items = []
    if DATABASE_URL:
        try:
            items = fetch_from_db()
        except Exception as e:
            resp.set_data(f"DB error: {e}")
            resp.status_code = 500
            return resp

    # 2) 바디로 직접 아이템 전달도 허용(운영 편의)
    if not items:
        try:
            payload = request.get_json(silent=True) or {}
            body_items = payload.get("items")
            if isinstance(body_items, list):
                items = body_items
        except Exception:
            pass

    # 3) 아무것도 없으면 실패로 보고
    if not items:
        resp.set_data("No items to set (provide DATABASE_URL or POST items)")
        resp.status_code = 400
        return resp

    ok = _set_redis(json.dumps(items, ensure_ascii=False), ex=3600)
    resp.set_data(f"upstash set: {ok}, count: {len(items)}")
    resp.status_code = 200 if ok else 500
    return resp
