from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
import os
import shutil

from cloudscraper import CloudScraper, create_scraper
from loguru import logger
from tqdm.auto import tqdm

from utils import remove_all_non_ntfs_symbols


DOWNLOADS_DIR = 'Downloads'


@dataclass
class Season:
    title: str
    episodes_urls: list[str]


def download_video(url: str, path: os.PathLike, scraper: CloudScraper):
    with scraper.get(url, stream=True) as r:
        total_length = int(r.headers.get("Content-Length"))
        with tqdm.wrapattr(r.raw, "read", total=total_length, desc="") as raw:
            with open(path, 'wb') as file:
                shutil.copyfileobj(raw, file)


def main():
    scraper = create_scraper(delay=1, browser={'custom': 'ScraperBot/1.0', })

    # Получаем от пользователя необходимые данные
    anime_url = input('Введите ссылку на аниме с jut.su (пр.: https://jut.su/baki/): ')
    season_from = int(
        input('С какого сезона начинать скачивание? Пропустите этот шаг, если с первого: ') or 1
    )
    episode_from = int(
        input(f'С какой серии {season_from}-го сезона начинать скачивание? '
              f'Пропустите этот шаг, если с первой: ') or 1
    )
    season_to = int(
        input('До какого сезона скачивать? Пропустите этот шаг, если до последнего: ') or 1e9
    )
    episode_to = int(
        input('До какой серии выбранного сезона скачивать? Пропустите этот шаг, если до последней: ') or 1e9
    )

    # Парсим страницу аниме
    response = scraper.get(anime_url)
    soup = BeautifulSoup(response.text, 'lxml')

    # Название аниме
    anime_title = soup.find('h1', {'class': 'anime_padding_for_title'}).text
    anime_title = (
        anime_title
        .replace('Смотреть', '')
        .replace('все серии', '')
        .replace('и сезоны', '').strip()
    )
    logger.info(f'Скачиваем: {anime_title}')

    # Весь сериал в одном объекте
    seasons = [
        Season(
            title=season_title.text,
            episodes_urls=[],
        ) for season_title in soup.find_all('h2', class_=['the-anime-season'])
    ]

    # Если сезон всего один
    if len(seasons) == 0:
        seasons.append(
            Season(
                title=anime_title,
                episodes_urls=[],
            )
        )
    logger.info(f'Сезонов: {len(seasons)}')

    # Все эпизоды
    episodes_soup = soup.find_all('a', class_=['short-btn black video the_hildi', 'short-btn green video the_hildi'])
    logger.info(f'Всего серий: {len(episodes_soup)}')

    # Временные переменные
    current_season_index = -1
    current_episode_class = None

    # Перебираем эпизоды
    for ep in episodes_soup:

        # Если текущий класс эпизода не совпадает с прошлым - мы закончили сериал
        if ep['class'] != current_episode_class:
            # Сохраняем класс эпизода
            current_episode_class = ep['class']

            # Инкрементируем номер сезона, с которым работаем
            current_season_index += 1

        # Добавляем ссылку на серию в список серий сезона
        url = 'https://jut.su' + ep['href']
        seasons[current_season_index].episodes_urls.append(url)

    # Создаём папку сериала
    anime_path = Path(DOWNLOADS_DIR, remove_all_non_ntfs_symbols(anime_title))
    anime_path.mkdir(exist_ok=True)

    # Скачиваем
    for i, season in enumerate(seasons):
        season_number = i + 1

        # Если этот сезон скачивать не нужно
        if season_number < season_from or season_number > season_to:
            continue

        # Создаём папку сезона
        season_path = Path(anime_path, remove_all_non_ntfs_symbols(season.title))
        season_path.mkdir(exist_ok=True)

        # Скачиваем сезон: перебираем серии
        for j, episode_url in enumerate(season.episodes_urls):
            episode_number = j + 1

            # Если этот эпизод скачивать не нужно
            if (
                season_number == season_from and episode_number < episode_from
            ) or (
                (season_number == season_to or season_number == len(seasons)) and episode_number > episode_to
            ):
                continue

            # Парсим страницу эпизода
            response = scraper.get(episode_url)
            soup = BeautifulSoup(response.content, 'lxml')

            # Получаем название эпизода
            try:
                episode_title = soup.find('div', {'class': 'video_plate_title'}).find('h2').text

            # Если названия нет - получаем что-то вроде "2 сезон 20 серия"
            except AttributeError:
                episode_title = soup.find('span', {'itemprop': 'name'}).text
                episode_title = episode_title.replace('Смотреть', '').replace(anime_title, '').strip()

            # Получаем ссылку на видео
            video_url = soup.find('source')['src']

            # Скачиваем видео
            video_path = Path(season_path, remove_all_non_ntfs_symbols(f'[#{episode_number}] {episode_title}.mp4'))
            episode_slug = f'{anime_title} - {season.title} - {episode_title} (#{episode_number})'
            try:
                logger.info(f'[⏳] {episode_slug}')
                download_video(url=video_url, path=video_path, scraper=scraper)
                logger.success(f'[☑️] {episode_slug}')

            except Exception as e:
                logger.exception(e)
                exit()


if __name__ == '__main__':
    main()
