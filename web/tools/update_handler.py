import threading, os
from datetime import datetime
from flask import request, jsonify
from werkzeug.utils import secure_filename

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CONFIG_PATH = os.path.join(_BASE_DIR, 'config.py')
_UPLOAD_DIR = os.path.join(_BASE_DIR, 'data', 'temp_update')

def handle_get_changelog():
    """获取更新日志 - 通过 GitHub API 镜像"""
    try:
        from web.tools.updater import get_updater
        updater = get_updater()
        commits = updater._fetch_api('/commits?per_page=30')
        if not commits or not isinstance(commits, list):
            return jsonify({'success': False, 'message': 'GitHub API 请求失败，请稍后重试', 'data': []})

        result = []
        for c in commits:
            info = c.get('commit')
            if not info:
                continue
            author = info.get('author', {})
            date_str = author.get('date', '')
            try:
                fmt_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S') if date_str else '未知时间'
            except:
                fmt_date = '未知时间'
            result.append({
                'sha': c.get('sha', '')[:8],
                'message': info.get('message', '').strip(),
                'author': author.get('name', '未知'),
                'date': fmt_date,
                'url': c.get('html_url', ''),
                'full_sha': c.get('sha', '')
            })

        return jsonify({'success': True, 'data': result, 'total': len(result)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取更新日志失败: {e}'}), 500

def handle_get_current_version():
    from web.tools.updater import get_updater
    return jsonify({'success': True, 'data': get_updater().get_version_info()})

def handle_check_update():
    from web.tools.updater import get_updater
    return jsonify({'success': True, 'data': get_updater().check_for_updates()})

def handle_start_update():
    data = request.get_json() or {}
    from web.tools.updater import get_updater
    updater = get_updater()
    if data.get('mirror'):
        updater.set_custom_mirror(data['mirror'])

    skip_backup = data.get('skip_backup', False)
    
    def do_update():
        try:
            if data.get('force'):
                updater.force_update(skip_backup=skip_backup)
            elif data.get('version'):
                updater.update_to_version(data['version'], skip_backup=skip_backup)
            else:
                updater.update_to_latest(skip_backup=skip_backup)
        except Exception as e:
            updater._report_progress('failed', f'更新出错: {e}', 0)
    
    threading.Thread(target=do_update, daemon=True).start()
    return jsonify({'success': True, 'message': '更新已开始'})

def handle_get_update_status():
    from web.tools.updater import get_updater
    return jsonify({'success': True, 'data': get_updater().get_progress()})

def handle_get_update_progress():
    from web.tools.updater import get_updater
    return jsonify({'success': True, 'data': get_updater().get_progress()})

def handle_get_download_sources():
    from web.tools.updater import get_updater, GITHUB_FILE_MIRRORS
    updater = get_updater()
    return jsonify({'success': True, 'data': {
        'mirrors': GITHUB_FILE_MIRRORS,
        'custom_mirror': updater.custom_mirror,
    }})

def handle_set_download_source():
    data = request.get_json() or {}
    from web.tools.updater import get_updater
    get_updater().set_custom_mirror(data.get('mirror', ''))
    return jsonify({'success': True, 'message': '已保存镜像设置'})

def handle_test_download_source():
    """Not used in new mirror system"""
    return jsonify({'success': True, 'data': {'message': '请使用更新功能直接测试'}})

def handle_apply_config_diff():
    """应用配置差异补全"""
    data = request.get_json() or {}
    missing = data.get('missing', [])
    if not missing:
        return jsonify({'success': False, 'message': '没有需要补全的配置项'})
    from web.tools.updater import get_updater
    result = get_updater().apply_config_diff(missing)
    return jsonify(result)

def handle_upload_update():
    """处理上传压缩包更新"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    if not file.filename.lower().endswith('.zip'):
        return jsonify({'success': False, 'message': '只支持 ZIP 格式的压缩包'}), 400
    
    try:
        # 确保上传目录存在
        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        
        # 保存文件
        filename = secure_filename(file.filename) or f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        filepath = os.path.join(_UPLOAD_DIR, filename)
        file.save(filepath)
        
        # 获取版本名（可选）
        version_name = request.form.get('version_name', '').strip() or None
        skip_backup = request.form.get('skip_backup', '').lower() in ('true', '1', 'yes')
        
        from web.tools.updater import get_updater
        updater = get_updater()
        
        def do_update():
            try:
                updater.update_from_upload(filepath, version_name, skip_backup=skip_backup)
            except Exception as e:
                updater._report_progress('failed', f'更新出错: {e}', 0)
        
        threading.Thread(target=do_update, daemon=True).start()
        return jsonify({'success': True, 'message': '上传成功，开始更新'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'上传失败: {e}'}), 500

# 配置解析相关代码已移至 updater.py
