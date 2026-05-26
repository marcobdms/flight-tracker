import asyncio
import logging
from datetime import date, timedelta
from sources.matan import Matan
from sources.datacrawler import DataCrawler
from sources.skyscrapper import SkyScrapper
from config import settings

logging.basicConfig(level=logging.INFO)

async def main():
    date_out = date.today() + timedelta(days=90)
    date_back = date_out + timedelta(days=14)
    origin = "CCS"
    destination = "BCN"
    
    print(f"--- API TEST: {origin}-{destination} | {date_out} to {date_back} ---")
    
    try:
        matan = Matan()
        print("Testing Matan...")
        res_m = await matan.search_flights(origin, destination, date_out, date_back)
        print(f"Matan returned {len(res_m)} results")
    except Exception as e:
        print(f"Matan error: {e}")

    try:
        sky = SkyScrapper()
        print("Testing SkyScrapper...")
        res_s = await sky.search_flights(origin, destination, date_out, date_back)
        print(f"SkyScrapper returned {len(res_s)} results")
    except Exception as e:
        print(f"SkyScrapper error: {e}")

    try:
        dc = DataCrawler()
        print("Testing DataCrawler...")
        res_d = await dc.search_flights(origin, destination, date_out, date_back)
        print(f"DataCrawler returned {len(res_d)} results")
    except Exception as e:
        print(f"DataCrawler error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
