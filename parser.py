from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import pandas as pd
from time import sleep
import re
from pathlib import Path


_TABS = {
        "Summary": {
            "params": {
                "team": "team-link",
                "league": "tournament-link",
                "goals": "goal",
                "shots": "shotsPerGame",
                "y_cards": "yellow-card-box",
                "r_cards": "red-card-box",
                "poss": "possession",
                "pass_success": "passSuccess",
                "won_pg": "aerialWonPerGame",
                "rating": "rating",
            },
            "id": "top-team-stats-summary",
        },
        "Defensive": {
            "params": {
                "team": "team-link",
                "league": "tournament-link",
                "shots_pg": "shotsConcededPerGame",
                "tackle_pg": "tacklePerGame",
                "interceptions_pg": "interceptionPerGame",
                "fouls_pg": "foulsPerGame",
                "offsides_pg": "offsideGivenPerGame",
                "rating": "rating",
            },
            "id": "top-team-stats-defensive",
        },
        "Offensive": {
            "params": {
                "team": "team-link",
                "league": "tournament-link",
                "shots_target_pg": "shotOnTargetPerGame",
                "dribble_pg": "dribbleWonPerGame",
                "foul_pg": "foulGivenPerGame",
                "rating": "rating",
            },
            "id": "top-team-stats-offensive",
        },
        "xG": {
            "params": {
                "team": "team-link",
                "league": "tournament-link",
                "xG": "xG",
                "goals_without_own": "goalExcOwn",
                "xGDiff": "xGDiff",
                "totalShots": "totalShots",
                "xGPerShot": "xGPerShot",
                "rating": "rating",
            },
            "id": "top-team-stats-xg",
        },
    }


_LINKS_LEAGUE = [
    "https://www.whoscored.com/regions/206/tournaments/4/spain-laliga",
    "https://www.whoscored.com/regions/252/tournaments/2/england-premier-league",
    "https://www.whoscored.com/regions/108/tournaments/5/italy-serie-a",
    "https://www.whoscored.com/regions/81/tournaments/3/germany-bundesliga",
    "https://www.whoscored.com/regions/74/tournaments/22/france-ligue-1",
]


_PARAMETERS_DICT = {
    "team": "team-link",
    "played": "p",
    "wins": "w",
    "draw": "d",
    "loss": "l",
    "goals": "gf",
    "goals_conceded": "ga",
    "goals_diff": "gd",
    "points": "pts",
}


def normalize_week(text: str) -> str:
    return (
        text.replace("–", "-")
            .replace("—", "-")
            .replace("\xa0", " ")   # NBSP
            .replace("\u2011", "-") # non-breaking hyphen
            .replace("  ", " ")
            .replace("\n▼","")
            .strip()
            .lower()                # робимо нижній регістр
    )


#Parser table statistics
def parser_table(rows: list, **kwargs) -> list:
    result = []

    for row in rows:
        data = {}
        try:
            for name, col in kwargs.items():
                text = row.find_element(By.CLASS_NAME, col).text
                if name == "team":
                    text = re.sub(r"\d+\.\s*", "", text)
                data[name] = text
            result.append(data)
        except:
            continue
    return result


# Get table statistics
def get_table_data(driver:webdriver,page_name,params,table_id):
    driver.find_element(By.LINK_TEXT, page_name).click()
    try:
        table_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, table_id))
        )
    except TimeoutException:
        print(f"⚠️ Таблиця '{page_name}' не знайдена")
        return []

    stats = []

    while True:
        try:
            table = WebDriverWait(table_container, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            rows = table.find_elements(By.TAG_NAME, "tr")

            stats.extend(parser_table(rows, **params))

            next_btn = table_container.find_element(By.ID, "next")
            if "disabled" in next_btn.get_attribute("class"):
                break

            driver.execute_script("arguments[0].click();", next_btn)
            WebDriverWait(driver, 10).until(EC.staleness_of(table))

        except (TimeoutException, StaleElementReferenceException):
            break

    return stats



#Skip pop-up window
def safe_click(driver: webdriver, by: By, value: str, timeout: int = 10) -> None:
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        ).click()
    except (TimeoutException, StaleElementReferenceException):
        pass


#Prser league standings
def parse_standings(table: list, **kwargs) -> list:
    stands = []
    for row in table:
        try:
            form = [res.text.lower() for res in row.find_element(By.CLASS_NAME, "form").find_elements(By.TAG_NAME, "a")]
            wins = form.count('w')
            draws = form.count('d')
            losses = form.count('l')
            team_data = {
                key: row.find_element(By.CLASS_NAME, value).text
                for key, value in kwargs.items()
            }

            team_data["wins_6"] = wins
            team_data["draws_6"] = draws
            team_data["losses_6"] = losses
            
            stands.append(team_data)
        except StaleElementReferenceException:
            continue
    return stands


def parse_team_results(name_folder,logger=print):
    logger("🚀 Запуск Chrome")
    name_folder = Path(name_folder)
    try:
        name_folder.mkdir(parents=True,exist_ok=True)
    except OSError as e:
        logger(f"Folder not create {e}")
    
    driver = webdriver.Chrome()
    driver.get("https://www.whoscored.com/statistics")

    # Skip pop-up
    safe_click(driver, By.CLASS_NAME, "Button__StyledButton-buoy__sc-a1qza5-0")
    safe_click(driver, By.CLASS_NAME, "webpush-swal2-close")

    # 1. Team stats
    all_stats = pd.DataFrame()

    for tab_name, tab_info in _TABS.items():
        logger(f"📊 Вкладка: {tab_name}")
        data = get_table_data(driver, tab_name, tab_info["params"], tab_info["id"])
        if not data:
            logger(f"⚠️ Немає даних: {tab_name}")
            continue
        df = pd.DataFrame(data)
        all_stats = df if all_stats.empty else pd.merge(all_stats, df, how="outer", on=["team", "league", "rating"])

    all_stats.to_csv(f"{name_folder}/whoscored_stats.csv", index=False)
    logger("✅ Дані збережено у 'whoscored_stats.csv'")

    # 2. Leagues standings
    league_dataframes = []
    for url in _LINKS_LEAGUE:
        logger(f"\n🌍 Парсимо лігу: {url}")
        driver.get(url)
        table_rows = driver.find_element(By.CLASS_NAME, "standings").find_elements(By.TAG_NAME, "tr")
        df = pd.DataFrame(parse_standings(table_rows, **_PARAMETERS_DICT))
        league_dataframes.append(df)

    all_leagues = pd.concat(league_dataframes, ignore_index=True)
    all_leagues.to_csv(f"{name_folder}/whoscored_leagues_standings.csv", index=False)
    logger("✅ Дані збережено у 'whoscored_leagues_standings.csv'")

    # Union stats and standings
    combined = pd.merge(all_stats, all_leagues, how="outer", on=["team", "goals"])
    combined.to_csv(f"{name_folder}/whoscored_combined.csv", index=False)
    logger("💾 Повні дані збережено у 'whoscored_combined.csv'")

    driver.quit()


def parse_last_week_matches(name_folder,logger=print):
    name_folder = Path(name_folder)
    try:
        name_folder.mkdir(parents=True,exist_ok=True)
    except OSError as e:
        logger(f"Folder not create {e}")
    
    driver = webdriver.Chrome()
    matchs = []
    for link in _LINKS_LEAGUE:
        driver.get(link)

        safe_click(driver, By.CLASS_NAME, "Button__StyledButton-buoy__sc-a1qza5-0")
        safe_click(driver, By.CLASS_NAME, "webpush-swal2-close")

        prev_btn = WebDriverWait(driver,10).until(
            EC.element_to_be_clickable((By.ID,"dayChangeBtn-prev"))
        )
        first_team = driver.find_element(By.CLASS_NAME,"Match-module_teamNameText__Dqv-G")
        prev_btn.click()

        WebDriverWait(driver,10).until(
            EC.staleness_of(first_team)
        )
        scores = driver.find_elements(By.CLASS_NAME,"Match-module_scoreBoard__L4SLm")
        results = []
        for score in scores:
            result = [el.text for el in score.find_element(By.CLASS_NAME,"Match-module_teams__sGVeq").find_elements(By.CLASS_NAME,"Match-module_teamNameText__Dqv-G")]
            score = score.find_element(By.CLASS_NAME,"Match-module_score__5Ghhj").text.split("\n")
            if score[0] == "-":
                continue
            result.insert(1,(2 if int(score[0])>int(score[1]) else 1 if int(score[0]) == int(score[1]) else 0))
            results.append(result)

        matchs.append(pd.DataFrame(results,columns=["home_team","result_match","away_team"]))


    df_matchs_result = pd.concat(matchs)
    df_matchs_result.to_csv(f"{name_folder}/whoscored_match_result.csv",index=False)

def parse_matches_by_week(name_folder, week, logger=print):
    """
    Парсить матчі з сайту whoscored.com за конкретний тиждень.
    
    :param name_folder: Папка для збереження CSV
    :param week: Тиждень у форматі '9 - 15 Dec 2025'
    :param logger: Функція для виводу логів (за замовчуванням print)
    """
    name_folder = Path(name_folder)
    name_folder.mkdir(parents=True, exist_ok=True)

    driver = webdriver.Chrome()
    matchs = []

    week = normalize_week(week)

    for i, link in enumerate(_LINKS_LEAGUE, start=1):
        logger(f"🌍 Ліга {i}/{len(_LINKS_LEAGUE)}: {link}")
        driver.get(link)

        # Закриваємо поп-апи
        safe_click(driver, By.CLASS_NAME, "Button__StyledButton-buoy__sc-a1qza5-0")
        safe_click(driver, By.CLASS_NAME, "webpush-swal2-close")
        selected_week_raw = driver.find_element(By.CLASS_NAME, "toggleDatePicker").text
        print(repr(selected_week_raw))
        # Отримуємо поточний тиждень
        try:
            selected_week = normalize_week(driver.find_element(By.CLASS_NAME, "toggleDatePicker").text)
        except:
            logger("❌ Не знайдено рядок тижня")
            continue

        steps = 0
        max_steps = 60

        # Прокручуємо назад, поки не знайдемо потрібний тиждень
        while week != selected_week and steps < max_steps:
            steps += 1
            logger(f"⏪ Поточний тиждень: {selected_week} (крок {steps}/{max_steps})")
            
            try:
                prev_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "dayChangeBtn-prev"))
                )
                # first_team = driver.find_element(By.CLASS_NAME, "Match-module_teamNameText__Dqv-G")
                prev_btn.click()

                # Чекаємо, поки рядок оновиться
                WebDriverWait(driver, 10).until(
                    lambda d: normalize_week(d.find_element(By.CLASS_NAME, "toggleDatePicker").text) != selected_week
                )

                selected_week = normalize_week(driver.find_element(By.CLASS_NAME, "toggleDatePicker").text)
            except (TimeoutException, StaleElementReferenceException):
                logger("❌ Не вдалося завантажити попередній тиждень")
                break

        if week != selected_week:
            logger(f"❌ Тиждень {week} не знайдено, пропуск ліги")
            continue

        # Збір результатів матчів
        try:
            scores = driver.find_elements(By.CLASS_NAME, "Match-module_scoreBoard__L4SLm")
            results = []
            for score in scores:
                teams = score.find_element(By.CLASS_NAME, "Match-module_teams__sGVeq")\
                             .find_elements(By.CLASS_NAME, "Match-module_teamNameText__Dqv-G")
                result = [el.text for el in teams]

                score_vals = score.find_element(By.CLASS_NAME, "Match-module_score__5Ghhj").text.split("\n")
                if score_vals[0] == "-":
                    continue

                # Вставляємо результат матчу: 2 – перемога господарів, 1 – нічия, 0 – перемога гостей
                result.insert(1, 2 if int(score_vals[0]) > int(score_vals[1])
                              else 1 if int(score_vals[0]) == int(score_vals[1])
                              else 0)
                results.append(result)

            if results:
                matchs.append(pd.DataFrame(results, columns=["home_team", "result_match", "away_team"]))
            else:
                logger("⚠️ Дані матчів відсутні для цієї ліги")
        except Exception as e:
            logger(f"⚠️ Не вдалося зібрати матчі для цієї ліги: {e}")

    if matchs:
        df_matchs_result = pd.concat(matchs, ignore_index=True)
        df_matchs_result.to_csv(f"{name_folder}/whoscored_match_result.csv", index=False)
        logger("✅ Дані матчів збережено")
    else:
        logger("⚠️ Дані матчів відсутні для всіх ліг")

    driver.quit()
