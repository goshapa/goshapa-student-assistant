import os
os.environ.setdefault('BOT_TOKEN', '123:test')
os.environ.setdefault('OWNER_TELEGRAM_ID', '1')
import unittest
from types import SimpleNamespace
from html import unescape
from services.assignment_details import instructions_text, assignment_pages


class AssignmentDetailsTests(unittest.TestCase):
    def assignment(self, description):
        return SimpleNamespace(name='Essay <draft>', description=description,
            html_url='https://example.com/courses/1/assignments/2', due_at=None,
            submission_types='online_upload,online_text_entry',
            is_missing=False, is_late=False, is_submitted=False)

    def test_html_materials_and_list(self):
        text = instructions_text('<p>Write an essay.</p><ul><li>500 words</li><li>PDF</li></ul>'
            '<a href="/files/42">Rubric</a><script>hidden()</script>', 'https://example.com/')
        self.assertIn('• 500 words', text)
        self.assertIn('https://example.com/files/42', text)
        self.assertNotIn('hidden()', text)

    def test_missing_description_and_submission_options(self):
        text = unescape(''.join(assignment_pages(self.assignment('<p><br></p>'), None)))
        self.assertIn('не добавил текстовое описание', text)
        self.assertIn('загрузить файл, ввести текст', text)

    def test_long_description_is_complete_and_caption_safe(self):
        description = 'Do & check 😀. ' * 1000
        pages = assignment_pages(self.assignment(description), None)
        self.assertGreater(len(pages), 1)
        self.assertIn(description.strip(), unescape(''.join(pages)))
        self.assertTrue(all(len(page.encode('utf-16-le')) // 2 < 900 for page in pages))
        self.assertIn('&lt;draft&gt;', pages[0])

    def test_media_only_description(self):
        text = instructions_text('<img alt="Essay rubric" src="/rubric.png">', 'https://example.com')
        self.assertIn('Медиа: Essay rubric', text)
