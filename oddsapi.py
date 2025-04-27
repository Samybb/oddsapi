# -*- coding: utf-8 -*-
"""
Created on Mon Apr 21 14:49:05 2025

@author: Sam
"""

import requests
import pandas as pd
from collections import defaultdict
import os

# Récupérer les valeurs depuis les variables d'environnement
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

# Vérifier si les variables ont bien été récupérées (c'est important pour éviter des erreurs)
if not BOT_TOKEN or not CHAT_ID or not API_KEY:
    raise ValueError("Un ou plusieurs secrets manquent dans l'environnement!")

REGION = "eu"
MARKET = "h2h"
SPORTS = {
    "Ligue 1": "soccer_france_ligue_one",
    "Premier League": "soccer_epl",
    "La Liga": "soccer_spain_la_liga",
    "Serie A": "soccer_italy_serie_a",
    "Bundesliga": "soccer_germany_bundesliga",
    "Champions league": "soccer_uefa_champs_league",
    "Europa league": "soccer_uefa_europa_league",
    "FA cup": "soccer_fa_cup"
}

# Liste des bookmakers souhaités (en minuscules pour comparaison)
BOOKMAKERS_DESIRES = ["betclic", "betsson", "unibet", "winamaxfr"]

BASE_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

def get_odds_by_bookmaker(sport_key, bookmaker_key):
    url = BASE_URL.format(sport=sport_key)
    params = {
        "apiKey": API_KEY,
        "regions": REGION,
        "markets": MARKET,
        "bookmakers": bookmaker_key,
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"Erreur {response.status_code} pour {bookmaker_key} sur {sport_key}")
            return []
        return response.json()
    except Exception as e:
        print(f"Erreur de requête pour {bookmaker_key}: {e}")
        return []

def format_bookmaker_name(b):
    return b.lower().replace(".", "").replace(" ", "").replace("-", "")

def find_best_odds(events):
    best_odds_dict = defaultdict(lambda: {"home": (0, ""), "draw": (0, ""), "away": (0, "")})
    for event in events:
        match = f"{event['home_team']} vs {event['away_team']}"
        for bookmaker in event.get("bookmakers", []):
            title = format_bookmaker_name(bookmaker["title"])
            for market in bookmaker.get("markets", []):
                if market["key"] == "h2h":
                    outcomes = market["outcomes"]
                    for i, outcome in enumerate(outcomes):
                        team = ["home", "draw", "away"][i]
                        if outcome["price"] > best_odds_dict[match][team][0]:
                            best_odds_dict[match][team] = (outcome["price"], title)
    return best_odds_dict

def calculate_surebets(best_odds_dict):
    rows = []
    for match, odds in best_odds_dict.items():
        inv_total = 0
        values = []
        for key in ["home", "draw", "away"]:
            odd, book = odds[key]
            inv_total += 1 / odd if odd else 1
            values.extend([odd, book])

        if all(v[0] > 0 for v in odds.values()):
            if inv_total < 1:
                values.append(round(inv_total, 4))
                rows.append([match] + values)
    return rows

def send_telegram_message(message, bot_token, chat_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Erreur Telegram: {response.text}")
    except Exception as e:
        print(f"Exception Telegram: {e}")

all_rows = []

print("Début du traitement...")
for ligue, sport_key in SPORTS.items():
    print(f"\nTraitement de {ligue} ({sport_key})...")
    best_odds_dict = defaultdict(lambda: {"home": (0, ""), "draw": (0, ""), "away": (0, "")})
    
    for bookmaker in BOOKMAKERS_DESIRES:
        data = get_odds_by_bookmaker(sport_key, bookmaker)
        if not data:
            continue
        temp_dict = find_best_odds(data)
        for match, odds in temp_dict.items():
            for team in ["home", "draw", "away"]:
                if odds[team][0] > best_odds_dict[match][team][0]:
                    best_odds_dict[match][team] = odds[team]

    surebet_rows = calculate_surebets(best_odds_dict)
    if surebet_rows:
        message = f"🎯 <b>Surebets détectés !</b>\n\n"
        message += f"🏆 Compétition : <b>{ligue}</b>\n\n"  # Ajout du nom de la ligue

        for row in surebet_rows:
            match, cote1, book1, coteN, bookN, cote2, book2, inv_total = row
            message += (
                f"⚽ <b>{match}</b>\n"
                f"1️⃣ {cote1} (@{book1})\n"
                f"➖ {coteN} (@{bookN})\n"
                f"2️⃣ {cote2} (@{book2})\n"
                f"🧮 Inverse total : <b>{inv_total}</b>\n"
                f"--------------------------------------\n"
            )

        send_telegram_message(message, BOT_TOKEN, CHAT_ID)

        all_rows.extend(surebet_rows)

# Enregistrement
df = pd.DataFrame(all_rows, columns=[
    "Match",
    "Cote 1", "Bookmaker 1",
    "Cote N", "Bookmaker N",
    "Cote 2", "Bookmaker 2",
    "Inverse total"
])
