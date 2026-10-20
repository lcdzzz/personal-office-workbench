"""Opt-in package acceptance in the real native webview, using isolated data."""
from __future__ import annotations

import io
import json
import platform
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

import server


def run_check(window, directory, url):
    import webview
    result = {'ok':False, 'architecture':platform.machine(), 'runtime':server.runtime_info(), 'checks':[]}
    origin = url.rsplit('/',1)[0]
    reference = directory / 'experience.md'
    reference.write_text('# Packaged workbench\nLinked task experience.\n', encoding='utf-8')
    title = 'Package acceptance linked task'

    def request(path, body=None, headers=None):
        data = json.dumps(body).encode() if isinstance(body,dict) else body
        req = Request(origin+path, data=data, headers={'Origin':origin, 'Content-Type':'application/json', **(headers or {})})
        with urlopen(req, timeout=10) as response:
            return response.read()

    def wait_for(check, label):
        deadline = time.monotonic()+40
        last = None
        while time.monotonic() < deadline:
            try:
                if check():
                    result['checks'].append(label)
                    return
            except Exception as error:
                last = error
            time.sleep(.1)
        raise AssertionError(f'{label} timed out: {last}')

    def task():
        return next((item for item in server.state_from_disk()['tasks'] if item.get('title')==title), None)

    try:
        if not window.events.loaded.wait(45):
            raise AssertionError('Native webview did not load')
        wait_for(lambda: window.evaluate_js("typeof S !== 'undefined' && S && !!document.querySelector('[data-nav=files]')"), 'native-window-loaded')
        existing = task()
        result['restoredTask'] = bool(existing)
        if existing:
            assert existing.get('linkedFiles') and existing.get('done'), 'Previous launch did not persist the completed linked task'
            result['checks'].append('restart-persistence')
        else:
            fixture = json.dumps({'title':title, 'path':str(reference), 'note':'Native package experience'})
            window.evaluate_js("""(() => {
              const f = FIXTURE;
              document.querySelector('[data-nav=tasks]').click();
              document.getElementById('tTitle').value=f.title;
              document.querySelector('#taskForm [data-link-add]').click();
              document.querySelector('#taskForm [data-link-path]').value=f.path;
              document.querySelector('#taskForm [data-link-note]').value=f.note;
              document.getElementById('taskForm').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
              return true;
            })()""".replace('FIXTURE',fixture))
            wait_for(lambda: task() and task()['linkedFiles'][0]['path']==str(reference).replace('\\','/'), 'create-task-and-link')
        window.evaluate_js("document.querySelector('[data-nav=files]').click(); true")
        wait_for(lambda: window.evaluate_js("!!document.querySelector('[data-linked-resource]') && document.querySelector('#view').textContent.includes('Package acceptance linked task')"), 'linked-files-index')
        window.evaluate_js("""(() => {
          document.querySelector('[data-act=linked-task]').click();
          document.querySelector('.mask [data-link-note]').value='Native package verified experience';
          document.querySelector('.mask [data-r="1"]').click(); return true;
        })()""")
        wait_for(lambda: task()['linkedFiles'][0]['note']=='Native package verified experience', 'edit-link-note')
        current = task()
        request('/api/linked-files/reveal', {'taskId':current['id'], 'path':current['linkedFiles'][0]['path']})
        result['checks'].append('show-in-file-manager')
        if not current.get('done'):
            window.evaluate_js("""(() => {
              document.querySelector('[data-nav=tasks]').click();
              document.querySelector('[data-act=tfilter][data-f=all]').click();
              document.querySelector('[data-act=toggle]').click(); return true;
            })()""")
            wait_for(lambda: task().get('done') and task().get('linkedFiles'), 'completed-task-retains-link')
        backup = request('/api/backup/export', b'')
        with zipfile.ZipFile(io.BytesIO(backup)) as archive:
            items = json.loads(archive.read('tasks.json'))['items']
            assert items[0]['linkedFiles'][0]['note']=='Native package verified experience'
        generation = str(server.state_from_disk()['generation'])
        request('/api/backup/import?mode=replace', backup, {'If-Match':generation})
        result['checks'].append('backup-export-import')
        window.evaluate_js("window.__packageReloadMarker = true; true")
        window.load_url(url)
        wait_for(lambda: window.evaluate_js("typeof window.__packageReloadMarker === 'undefined' && typeof S !== 'undefined' && S && S.tasks.some(t => t.title==='Package acceptance linked task' && t.done && t.linkedFiles.length===1)"), 'reload-persistence')
        result['renderer'] = webview.renderer
        result['port'] = int(origin.rsplit(':',1)[1])
        result['ok'] = True
    except Exception as error:
        result['error'] = repr(error)
    finally:
        (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        window.destroy()
