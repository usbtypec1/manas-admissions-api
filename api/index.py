from dataclasses import asdict, dataclass
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from flask import Flask
from flask_cors import CORS, cross_origin

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


@dataclass(frozen=True, slots=True)
class ApplicationRow:
    applied_at: datetime
    applicant_id: str
    exams_score: float
    additional_score: float
    rating: int
    is_passed: bool


@dataclass(frozen=True, slots=True)
class Department:
    id: int
    name: str
    faculty_name: str
    quota: int
    ratings: list[ApplicationRow]


def parse_rating_rows(soup: BeautifulSoup) -> list[ApplicationRow]:
    applications: list[ApplicationRow] = []
    for tr in soup.find('table').find_all('tr')[1:]:
        is_passed = tr.get('class') == ['bg-success']
        tds = tr.find_all('td')
        rating = int(tds[0].text)
        applicant_id = tds[1].text
        exams_score = float(tds[2].text)
        additional_score = float(tds[3].text)
        applied_at = datetime.strptime(tds[4].text, '%d/%m/%Y %H:%M:%S')
        applications.append(ApplicationRow(
            applied_at=applied_at,
            rating=rating,
            applicant_id=applicant_id,
            exams_score=exams_score,
            additional_score=additional_score,
            is_passed=is_passed,
        ))
    return applications


def parse_quota_in_ratings_page(soup: BeautifulSoup) -> int:
    for p in soup.find_all('p'):
        if 'КВОТА' in p.text:
            parts = p.text.strip().split('КВОТА: ')
            if not parts:
                continue
            quota = parts[-1]
            if not quota.isdigit():
                continue
            return int(quota)

    raise ValueError('Quota number is not found in ratings page')


def parse_department_name(soup: BeautifulSoup) -> tuple[str, str]:
    name = soup.find('h4', attrs={'class': 'modal-title'}).text
    name = name.strip()
    faculty_name, department_name = name.split('\n')
    return faculty_name.strip(), department_name.strip()


def parse_ratings_page(
        department_id: int,
        html: str,
) -> Department:
    soup = BeautifulSoup(html, 'lxml')
    rows = parse_rating_rows(soup)
    quota = parse_quota_in_ratings_page(soup)
    faculty_name, department_name = parse_department_name(soup)

    return Department(
        id=department_id,
        name=department_name,
        faculty_name=faculty_name,
        quota=quota,
        ratings=rows,
    )


def get_department_ratings(
        http_client: httpx.Client,
        department_id: int,
) -> Department | None:
    url = (
        'https://abiturient.manas.edu.kg/page/index.php'
        f'?r=site%2Fmonitoring-dep&id={department_id}'
    )
    response = http_client.get(url)
    if response.is_error:
        return
    return parse_ratings_page(
        department_id=department_id,
        html=response.text,
    )


@app.route('/departments/<int:department_id>')
@cross_origin()
def home(department_id: int):
    with httpx.Client() as http_client:
        department = get_department_ratings(http_client, department_id)

    if department is None:
        return {'error': 'Department not found'}, 404

    return asdict(department)
