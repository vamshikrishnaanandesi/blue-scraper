from bato_scraper import parse_image_urls_from_html


def test_parse_basic_images():
    html = '''
    <html><body>
      <div class="reader">
        <img src="/images/001.jpg" />
        <img data-src="https://cdn.example.com/manga/002.jpg" />
        <img srcset="https://cdn.example.com/manga/003.jpg 800w, https://cdn.example.com/manga/003_small.jpg 400w" />
        <img src="https://example.com/logo.png" class="site-logo" />
      </div>
    </body></html>
    '''
    out = parse_image_urls_from_html(html, base_url="https://bato.si/title/86663-en-grand-blue-dreaming-official/1680643-vol_11-ch_45")
    assert any('001.jpg' in u for u in out)
    assert any('002.jpg' in u for u in out)
    assert any('003.jpg' in u for u in out)
    # logo should be filtered out
    assert all('logo.png' not in u for u in out)
