"""Show the teacher's instructions without inventing missing requirements."""
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from utils.datetime_utils import to_tz
from utils.formatting import assignment_status_line


class InstructionParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts = []
        self.hidden = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ('p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n' + ('• ' if tag == 'li' else ''))
        if tag == 'td':
            self.parts.append(' | ')
        if tag == 'a' and attrs.get('href'):
            url = urljoin(self.base_url, attrs['href'])
            if urlparse(url).scheme in ('http', 'https'):
                self.links.append(url)
        if tag in ('img', 'iframe', 'video', 'audio'):
            self.parts.append('\n[Медиа: ' + (attrs.get('alt') or 'посмотри в Canvas') + ']\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def instructions_text(description, base_url):
    parser = InstructionParser(base_url)
    parser.feed(description or '')
    text = re.sub(r'[ \t\r\f\v]+', ' ', ''.join(parser.parts))
    text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
    if parser.links:
        text += '\n\nСсылки и материалы преподавателя:\n' + '\n'.join(dict.fromkeys(parser.links))
    return text.strip()


def split_text(text, limit=600):
    """Bound HTML-escaped and UTF-16 length for Telegram photo captions."""
    pages, current, size = [], '', 0
    for char in text:
        cost = max(len(escape(char)), len(char.encode('utf-16-le')) // 2)
        if size + cost > limit:
            pages.append(current)
            current, size = '', 0
        current += char
        size += cost
    if current:
        pages.append(current)
    return pages or ['']


def assignment_pages(assignment, course):
    due = to_tz(assignment.due_at).strftime('%d.%m.%Y %H:%M') if assignment.due_at else 'Не указан'
    formats = {'online_upload': 'загрузить файл', 'online_text_entry': 'ввести текст',
        'online_url': 'отправить ссылку', 'discussion_topic': 'ответить в обсуждении',
        'online_quiz': 'пройти тест', 'on_paper': 'сдать вне Canvas',
        'none': 'отправка в Canvas не предусмотрена', 'external_tool': 'через внешний сервис',
        'media_recording': 'записать аудио или видео', 'student_annotation': 'аннотировать документ'}
    kinds = [formats.get(s, s) for s in (assignment.submission_types or '').split(',') if s]
    description = instructions_text(assignment.description, assignment.html_url or '')
    text = (f'📄 {assignment.name}\n📚 {course.title if course else "Canvas"}\n'
            f'📅 Дедлайн: {due} (Ташкент)\n{assignment_status_line(assignment)}\n\n'
            f'📤 Как сдать: {", ".join(kinds) if kinds else "способ не указан"}\n\n'
            '📝 Что нужно сделать — описание преподавателя:\n'
            + (description or 'Преподаватель не добавил текстовое описание. Открой Canvas и проверь материалы курса.')
            + '\n\nЭто исходные инструкции без перевода. Требования из вложений здесь не извлечены.')
    return [escape(page) for page in split_text(text)]
