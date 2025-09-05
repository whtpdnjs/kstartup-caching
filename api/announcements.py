# api/announcements.py
import os, json, re, typing as t
from datetime import datetime
import requests
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
REDIS_KEY = "kstartup:announcements:v1"
HEADERS = {"Authorization": f"Bearer {REDIS_TOKEN}"}

def _redis_get(key: str) -> t.Optional[str]:
    if not (REDIS_URL and REDIS_TOKEN):
        return None
    r = requests.get(f"{REDIS_URL}/get/{key}", headers=HEADERS, timeout=10)
    if not r.ok:
        return None
    return r.json().get("result")

def _redis_set(key: str, val: str, ex: int = 3600) -> bool:
    if not (REDIS_URL and REDIS_TOKEN):
        return False
    r = requests.get(
        f"{REDIS_URL}/set/{key}/{requests.utils.quote(val, safe='')}",
        params={"ex": ex},
        headers=HEADERS,
        timeout=10,
    )
    return r.ok

def _fmt_date8(s: str) -> str:
    s = re.sub(r"[^0-9]", "", str(s or ""))
    if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s

def _server_filter(items, q: str, region: str, status_: str):
    arr = list(items)
    if q:
        qq = q.lower().strip()
        def hay(it):
            parts = [
                it.get("biz_pbanc_nm"), it.get("intg_pbanc_biz_nm"), it.get("pbanc_ctnt"),
                it.get("pbanc_ntrp_nm"), it.get("supt_biz_clsfc")
            ]
            return " ".join([str(x or "").lower() for x in parts])
        arr = [it for it in arr if qq in hay(it)]
    if region:
        arr = [it for it in arr if region in str(it.get("supt_regin") or "")]
    if status_:
        arr = [it for it in arr if str(it.get("rcrt_prgs_yn") or "") == status_]
    return arr

def _seed_sample() -> list[dict]:
    # 캐시 미스 시 보여줄 샘플(질문에 주신 2건)
    return [
      {
        "aply_excl_trgt_ctnt": "없음",
        "aply_mthd_onli_rcpt_istc": "https://docs.google.com/forms/d/e/1FAIpQLSdeoKE2BFn5yu1hOWKJtYwuzGE6p5yuTbOKNu24cbK6jSdauA/viewform?usp=sharing&ouid=111321243853730643304",
        "aply_trgt": "연구기관,일반기업",
        "aply_trgt_ctnt": "기술 이전을 받은 기업, 교원 창업 기업",
        "biz_enyy": "7년미만",
        "biz_gdnc_url": "https://www.ntis.go.kr/ThMain.do",
        "biz_pbanc_nm": "2025년 범부처 공공기술이전 사업화 로드쇼 릴레이IR 참여기업 모집",
        "biz_prch_dprt_nm": "미래혁신그룹",
        "biz_trgt_age": "만 20세 미만,만 20세 이상 ~ 만 39세 이하,만 40세 이상",
        "detl_pg_url": "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn=174652",
        "id": 1,
        "intg_pbanc_biz_nm": "2025년 범부처 공공기술이전 사업화 로드쇼",
        "intg_pbanc_yn": "N",
        "pbanc_ctnt": "기술이전 및 교원창업 기업 대상으로 투자유치 기회를 제공합니다. ",
        "pbanc_ntrp_nm": "와이앤아처 주식회사",
        "pbanc_rcpt_bgng_dt": "20250813",
        "pbanc_rcpt_end_dt": "20250831",
        "pbanc_sn": 174652,
        "prch_cnpl_no": "07088331581",
        "rcrt_prgs_yn": "Y",
        "sprv_inst": "민간",
        "supt_biz_clsfc": "정책자금",
        "supt_regin": "전국"
      },
      {
        "aply_mthd_eml_rcpt_istc": "XHpc/H/Ocerzbp06c7lyOw==",
        "aply_trgt": "일반기업",
        "aply_trgt_ctnt": "한진과 사업협력을 희망하는 창업 7년 미만 스타트업.",
        "biz_enyy": "7년미만",
        "biz_gdnc_url": "ccei.creativekorea.or.kr/incheon/custom/notice_view.do?no=36014&rnum=1677&kind=my&sPtime=my",
        "biz_pbanc_nm": "2025 한진 오픈이노베이션 프로그램 참여기업 모집공고",
        "biz_prch_dprt_nm": "글로벌오픈이노베이션팀",
        "biz_trgt_age": "만 20세 이상 ~ 만 39세 이하,만 40세 이상",
        "detl_pg_url": "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn=174646",
        "id": 3,
        "intg_pbanc_biz_nm": "2025 한진 오픈이노베이션 프로그램 참여기업 모집공고",
        "intg_pbanc_yn": "N",
        "pbanc_ctnt": "(재)인천창조경제혁신센터에서는 한진과 협업을 희망하는 우수 기업을 발굴하고 지원하기 위하여 「2025 한진 오픈이노베이션 프로그램」을 모집하오니 많은 관심과 참여 바랍니다",
        "pbanc_ntrp_nm": "(재)인천창조경제혁신센터",
        "pbanc_rcpt_bgng_dt": "20250813",
        "pbanc_rcpt_end_dt": "20250820",
        "pbanc_sn": 174646,
        "prch_cnpl_no": "0324585027",
        "rcrt_prgs_yn": "Y",
        "sprv_inst": "공공기관",
        "supt_biz_clsfc": "사업화",
        "supt_regin": "전국"
      }
    ]

def _with_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Cache-Control"] = "s-maxage=300, stale-while-revalidate=600"
    return resp

@app.route("/", methods=["GET", "OPTIONS"])
def announcements():
    if request.method == "OPTIONS":
        return _with_cors(make_response(("", 204)))

    raw = _redis_get(REDIS_KEY)
    if not raw:
        items = _seed_sample()
        _redis_set(REDIS_KEY, json.dumps(items, ensure_ascii=False), ex=3600)
    else:
        items = json.loads(raw)

    q = request.args.get("q", "")
    region = request.args.get("region", "")
    status_ = request.args.get("status", "")
    filtered = _server_filter(items, q, region, status_)

    for it in filtered:
        it["pbanc_rcpt_bgng_dt_fmt"] = _fmt_date8(it.get("pbanc_rcpt_bgng_dt"))
        it["pbanc_rcpt_end_dt_fmt"] = _fmt_date8(it.get("pbanc_rcpt_end_dt"))

    resp = jsonify({"count": len(filtered), "items": filtered})
    return _with_cors(resp)
