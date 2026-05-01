#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, json, shutil, zipfile, logging, requests, fnmatch
from datetime import datetime
from pathlib import Path

GITHUB_REPO = "ElainaCore/ElainaBot"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_DOWNLOAD_URL = f"https://github.com/{GITHUB_REPO}/archive/main.zip"
GITHUB_SHA_URL = f"https://codeload.github.com/{GITHUB_REPO}/zip/{{version}}"

GITHUB_API_MIRRORS = [
    f'https://api.github.com/repos/{GITHUB_REPO}',
    f'https://ghproxy.cc/https://api.github.com/repos/{GITHUB_REPO}',
    f'https://gh-proxy.com/https://api.github.com/repos/{GITHUB_REPO}',
    f'https://ghproxy.net/https://api.github.com/repos/{GITHUB_REPO}',
    f'https://mirror.ghproxy.com/https://api.github.com/repos/{GITHUB_REPO}',
]

GITHUB_FILE_MIRRORS = [
    'https://ghproxy.cc/',
    'https://gh-proxy.com/',
    'https://ghproxy.net/',
    'https://mirror.ghproxy.com/',
    'https://ghfast.top/',
]

class FrameworkUpdater:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent.absolute()
        self.version_file = self.base_dir / "data" / "version.json"
        self.settings_file = self.base_dir / "data" / "update_settings.json"
        (self.base_dir / "data").mkdir(exist_ok=True)
        
        self.config = self._load_config()
        self.current_version = self._load_version()
        self.custom_mirror = self._load_setting('custom_mirror', '')
        self.current_progress = {'stage': 'idle', 'message': '', 'progress': 0, 'is_updating': False}
    
    def _load_config(self):
        try:
            from config import PROTECTED_FILES
            return {'skip_files': PROTECTED_FILES, 'backup_enabled': True, 'backup_dir': 'data/backup'}
        except:
            return {'skip_files': ['config.py', 'data/', 'plugins/'], 'backup_enabled': True, 'backup_dir': 'data/backup'}
    
    def _load_version(self):
        try:
            return json.load(open(self.version_file, encoding='utf-8')).get('version', 'unknown')
        except:
            return 'unknown'
    
    def _save_version(self, version):
        try:
            json.dump({'version': version, 'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, 
                     open(self.version_file, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            self.current_version = version
        except:
            pass
    
    def _load_setting(self, key, default):
        try:
            return json.load(open(self.settings_file, encoding='utf-8')).get(key, default)
        except:
            return default
    
    def _save_setting(self, key, value):
        try:
            data = json.load(open(self.settings_file, encoding='utf-8')) if self.settings_file.exists() else {}
            data[key] = value
            json.dump(data, open(self.settings_file, 'w', encoding='utf-8'), indent=2)
        except:
            pass
    
    def _report_progress(self, stage, message, progress=0, config_diff=None):
        self.current_progress = {'stage': stage, 'message': message, 'progress': progress, 
                                  'is_updating': stage not in ('idle', 'completed', 'failed'),
                                  'config_diff': config_diff}
    
    def get_progress(self):
        return self.current_progress.copy()
    
    def get_version_info(self):
        try:
            info = json.load(open(self.version_file, encoding='utf-8'))
            info['custom_mirror'] = self.custom_mirror
            return info
        except:
            return {'version': self.current_version, 'update_time': 'unknown', 'custom_mirror': self.custom_mirror}

    def set_custom_mirror(self, mirror):
        self.custom_mirror = mirror or ''
        self._save_setting('custom_mirror', self.custom_mirror)

    def _fetch_api(self, path=''):
        """通过多个 GitHub API 镜像获取数据"""
        headers = {'User-Agent': 'ElainaBot/1.0', 'Accept': 'application/vnd.github+json'}
        urls = [base + path for base in GITHUB_API_MIRRORS]
        for u in urls:
            try:
                resp = requests.get(u, headers=headers, timeout=15)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                continue
        return None

    def _pick_download_url(self, original_url):
        """选择可用的文件镜像"""
        if self.custom_mirror:
            return self.custom_mirror.rstrip('/') + '/' + original_url
        for m in GITHUB_FILE_MIRRORS:
            try:
                test_url = m.rstrip('/') + '/' + original_url
                resp = requests.head(test_url, timeout=5, allow_redirects=True)
                if resp.status_code < 400:
                    return test_url
            except Exception:
                continue
        return original_url

    def check_for_updates(self):
        try:
            self._report_progress('checking', '正在检查更新...', 0)
            commits = self._fetch_api('/commits?per_page=10')
            if not commits or not isinstance(commits, list):
                self._report_progress('idle', '', 0)
                return {'has_update': False, 'error': '无法获取更新信息'}

            latest = commits[0].get('sha', '')[:8]
            current = self.current_version[:8] if len(self.current_version) >= 8 else self.current_version
            has_update = (current != latest and self.current_version != 'unknown') or self.current_version == 'unknown'

            self._report_progress('idle', '', 0)
            return {'has_update': has_update, 'latest_version': latest, 'current_version': self.current_version,
                    'changelog': commits[:10], 'error': None}
        except Exception as e:
            self._report_progress('idle', '', 0)
            return {'has_update': False, 'error': str(e)}
    
    def download_update(self, version):
        try:
            self._report_progress('downloading', '正在下载...', 5)
            temp_dir = self.base_dir / "data" / "temp_update"
            temp_dir.mkdir(exist_ok=True)
            zip_file = temp_dir / f"{version}.zip"

            raw_url = GITHUB_SHA_URL.format(version=version)
            url = self._pick_download_url(raw_url)
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()
            
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            with open(zip_file, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self._report_progress('downloading', f'下载中... {downloaded*100//total}%', 10 + downloaded*30//total)
            
            self._report_progress('downloading', '下载完成', 40)
            return str(zip_file)
        except Exception as e:
            self._report_progress('failed', f'下载失败: {e}', 0)
            return None
    
    def backup_current_version(self):
        if not self.config.get('backup_enabled'):
            return 'disabled'
        try:
            backup_dir = self.base_dir / self.config['backup_dir']
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / f"backup_{self.current_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            
            skip_prefixes = ('plugins', 'data/backup', 'data\\backup', 'data/temp_update', 'data\\temp_update')
            skip_contains = ('.git', '__pycache__')
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(self.base_dir):
                    rel = os.path.relpath(root, self.base_dir)
                    if any(rel.startswith(p) for p in skip_prefixes) or any(s in rel for s in skip_contains):
                        dirs[:] = []
                        continue
                    dirs[:] = [d for d in dirs if not any(os.path.relpath(os.path.join(root, d), self.base_dir).startswith(p) for p in skip_prefixes)]
                    for f in files:
                        fp = os.path.join(root, f)
                        if not any(s in fp for s in skip_contains):
                            zf.write(fp, os.path.relpath(fp, self.base_dir))
            return str(backup_file)
        except Exception as e:
            logging.error(f"备份失败: {e}")
            return None
    
    def _should_skip(self, path):
        path = path.replace('\\', '/')
        for p in self.config.get('skip_files', []):
            p = p.replace('\\', '/')
            if path == p.rstrip('/') or path.startswith(p.rstrip('/') + '/') or fnmatch.fnmatch(path, p):
                return True
        return False
    
    def apply_update(self, zip_file, version, skip_backup=False):
        result = {'success': False, 'message': '', 'updated': 0, 'skipped': 0, 'config_diff': None}
        try:
            if skip_backup:
                self._report_progress('backing_up', '跳过备份...', 45)
                backup = 'skipped'
            else:
                self._report_progress('backing_up', '正在备份...', 45)
                backup = self.backup_current_version()
                if not backup and self.config.get('backup_enabled'):
                    self._report_progress('failed', '备份失败', 0)
                    return result
            
            self._report_progress('updating', '正在解压...', 55)
            temp = self.base_dir / "data" / "temp_extract"
            if temp.exists():
                shutil.rmtree(temp)
            temp.mkdir(parents=True)
            
            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(temp)
            
            # 处理 GitHub 格式（有根目录）
            items = list(temp.iterdir())
            source = items[0] if len(items) == 1 and items[0].is_dir() else temp
            
            # 检查配置差异（用新版 config.py 对比本地）
            new_config = source / "config.py"
            local_config = self.base_dir / "config.py"
            if new_config.exists() and local_config.exists():
                result['config_diff'] = self._check_config_diff(str(new_config), str(local_config))
            
            self._report_progress('updating', '正在更新文件...', 60)
            for root, _, files in os.walk(source):
                for f in files:
                    src = os.path.join(root, f)
                    rel = os.path.relpath(src, source)
                    if self._should_skip(rel):
                        result['skipped'] += 1
                        continue
                    dst = self.base_dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    result['updated'] += 1
            
            shutil.rmtree(temp, ignore_errors=True)
            os.remove(zip_file) if os.path.exists(zip_file) else None
            
            result['success'] = True
            result['message'] = f'更新成功！更新 {result["updated"]} 个文件，跳过 {result["skipped"]} 个'
            self._report_progress('completed', result['message'], 100, result['config_diff'])
        except Exception as e:
            result['message'] = f'更新失败: {e}'
            self._report_progress('failed', result['message'], 0)
        return result
    
    def _check_config_diff(self, new_config_path, local_config_path):
        """检查新旧配置文件差异，返回缺失项"""
        import re, ast
        try:
            with open(new_config_path, 'r', encoding='utf-8') as f:
                new_content = f.read()
            with open(local_config_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            def parse_config(content):
                vars_dict, dicts_dict = {}, {}
                lines = content.split('\n')
                current_dict, dict_content, brace_count = None, [], 0
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        if current_dict:
                            dict_content.append(line)
                        continue
                    if current_dict:
                        dict_content.append(line)
                        brace_count += line.count('{') - line.count('}')
                        if brace_count == 0:
                            try:
                                match = re.match(r'^[A-Z_][A-Z0-9_]*\s*=\s*(\{.*\})', '\n'.join(dict_content), re.DOTALL)
                                if match:
                                    dicts_dict[current_dict] = ast.literal_eval(match.group(1))
                            except:
                                pass
                            current_dict, dict_content = None, []
                        continue
                    dict_match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*\{', stripped)
                    if dict_match:
                        current_dict = dict_match.group(1)
                        dict_content = [line]
                        brace_count = line.count('{') - line.count('}')
                        if brace_count == 0:
                            try:
                                match = re.match(r'^[A-Z_][A-Z0-9_]*\s*=\s*(\{.*\})', stripped)
                                if match:
                                    dicts_dict[current_dict] = ast.literal_eval(match.group(1))
                            except:
                                pass
                            current_dict, dict_content = None, []
                        continue
                    var_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)(?:\s*#.*)?$', stripped)
                    if var_match:
                        name, value = var_match.group(1), var_match.group(2).strip()
                        if not value.startswith(('{', '[')):
                            try:
                                vars_dict[name] = ast.literal_eval(value)
                            except:
                                vars_dict[name] = value
                return vars_dict, dicts_dict
            
            new_vars, new_dicts = parse_config(new_content)
            local_vars, local_dicts = parse_config(local_content)
            
            missing = []
            for k, v in new_vars.items():
                if k not in local_vars:
                    missing.append({'type': 'var', 'name': k, 'value': repr(v)})
            for k, v in new_dicts.items():
                if k not in local_dicts:
                    missing.append({'type': 'dict', 'name': k, 'value': repr(v)})
                else:
                    for key, val in v.items():
                        if key not in local_dicts[k]:
                            missing.append({'type': 'dict_key', 'dict': k, 'key': key, 'value': repr(val)})
            
            return {'has_diff': len(missing) > 0, 'missing': missing, 'count': len(missing)}
        except:
            return None
    
    def apply_config_diff(self, missing_items):
        """将缺失的配置项追加到 config.py"""
        try:
            config_path = self.base_dir / "config.py"
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 备份
            backup_path = str(config_path) + '.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            additions = ['\n# ===== 自动补全的配置项 =====']
            dict_hints = []
            for item in missing_items:
                if item['type'] == 'var':
                    additions.append(f"{item['name']} = {item['value']}")
                elif item['type'] == 'dict':
                    additions.append(f"{item['name']} = {item['value']}")
                elif item['type'] == 'dict_key':
                    dict_hints.append(f"# {item['dict']}['{item['key']}'] = {item['value']}")
            
            if dict_hints:
                additions.append('\n# ===== 字典内缺失的键（请手动添加）=====')
                additions.extend(dict_hints)
            
            new_content = content.rstrip() + '\n' + '\n'.join(additions) + '\n'
            
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return {'success': True, 'count': len(missing_items)}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def update_to_version(self, version, skip_backup=False):
        self._report_progress('preparing', f'准备更新到 {version}...', 0)
        zip_file = self.download_update(version)
        if not zip_file:
            return {'success': False, 'message': '下载失败'}
        result = self.apply_update(zip_file, version, skip_backup=skip_backup)
        if result['success']:
            self._save_version(version)
        return result
    
    def update_to_latest(self, skip_backup=False):
        check = self.check_for_updates()
        if check.get('error'):
            return {'success': False, 'message': f"检查失败: {check['error']}"}
        if not check['has_update']:
            return {'success': False, 'message': '已是最新版本'}
        return self.update_to_version(check['latest_version'], skip_backup=skip_backup)
    
    def force_update(self, skip_backup=False):
        """强制更新到最新版本"""
        try:
            self._report_progress('checking', '获取最新版本...', 0)
            commits = self._fetch_api('/commits?per_page=1')
            if not commits or not isinstance(commits, list):
                return {'success': False, 'message': '无法获取版本信息'}
            latest = commits[0].get('sha', '')[:8]
            return self.update_to_version(latest, skip_backup=skip_backup)
        except Exception as e:
            self._report_progress('failed', f'获取版本失败: {e}', 0)
            return {'success': False, 'message': str(e)}
    
    def update_from_upload(self, zip_file_path, version_name=None, skip_backup=False):
        """从上传的压缩包更新"""
        try:
            self._report_progress('preparing', '准备从上传的压缩包更新...', 0)
            
            # 验证文件
            if not os.path.exists(zip_file_path):
                self._report_progress('failed', '上传的文件不存在', 0)
                return {'success': False, 'message': '上传的文件不存在'}
            
            if not zipfile.is_zipfile(zip_file_path):
                self._report_progress('failed', '无效的压缩包格式', 0)
                return {'success': False, 'message': '无效的压缩包格式，请上传 ZIP 文件'}
            
            # 生成版本号
            version = version_name or f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self._report_progress('updating', '正在应用更新...', 40)
            result = self.apply_update(zip_file_path, version, skip_backup=skip_backup)
            
            if result['success']:
                self._save_version(version)
            
            return result
        except Exception as e:
            self._report_progress('failed', f'更新失败: {e}', 0)
            return {'success': False, 'message': str(e)}

_updater = None
def get_updater():
    global _updater
    if not _updater:
        _updater = FrameworkUpdater()
    return _updater
