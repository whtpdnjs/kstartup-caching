import { Redis } from '@upstash/redis';
import fetch from 'node-fetch';

const redis = new Redis({
    url: process.env.UPSTASH_REDIS_REST_URL,
    token: process.env.UPSTASH_REDIS_REST_TOKEN,
});

const API_KEY = process.env.API_KEY;
const API_URL = `https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01?serviceKey=${API_KEY}&page=1&perPage=100&cond[intg_pbanc_yn::EQ]=N&cond[supt_regin::LIKE]=%EC%A0%84%EA%B5%AD&returnType=json`;

const CACHE_KEY = "kstartup-data";
const CACHE_EXPIRATION_SECONDS = 3600; // 1시간 (초 단위)

export default async function handler(req, res) {
    try {
        // 1. Upstash Redis에서 캐시 데이터 확인
        const cachedData = await redis.get(CACHE_KEY);
        if (cachedData) {
            console.log("Using cached data.");
            return res.status(200).json(cachedData);
        }

        // 2. 캐시 데이터가 없으면 외부 API 호출
        console.log("Fetching new data from API.");
        const apiResponse = await fetch(API_URL);
        const apiData = await apiResponse.json();

        // 3. API 데이터를 Upstash Redis에 캐싱
        await redis.set(CACHE_KEY, apiData, { ex: CACHE_EXPIRATION_SECONDS });
        console.log("New data cached.");

        // 4. 클라이언트에게 데이터 반환
        res.status(200).json(apiData);

    } catch (error) {
        console.error("Error fetching or caching data:", error);
        res.status(500).json({ error: "Failed to fetch data." });
    }
}