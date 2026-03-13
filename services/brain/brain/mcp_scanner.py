import ast
import os
from pathlib import Path
from typing import Dict, List, Tuple


class MCPSecurityScanner:
    DANGEROUS_IMPORTS = {
        'subprocess', 'os.system', 'eval', 'exec', 'compile',
        '__import__', 'importlib', 'pickle', 'shelve'
    }

    NETWORK_IMPORTS = {
        'urllib', 'requests', 'httpx', 'aiohttp', 'socket',
        'http.client', 'ftplib', 'smtplib'
    }

    FILESYSTEM_IMPORTS = {
        'os.path', 'pathlib', 'shutil', 'tempfile', 'glob'
    }

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.findings: List[Dict] = []
        self.risk_score = 0

    def scan(self) -> Tuple[int, List[Dict]]:
        """Scan repository and return (risk_score, findings)"""
        py_files = list(self.repo_path.rglob("*.py"))

        for py_file in py_files:
            self._scan_file(py_file)

        self._calculate_risk_score()
        return self.risk_score, self.findings

    def _scan_file(self, filepath: Path):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(filepath))
        except Exception as e:
            self.findings.append({
                'file': str(filepath),
                'type': 'parse_error',
                'severity': 'medium',
                'message': f'Failed to parse: {e}'
            })
            return

        for node in ast.walk(tree):
            self._check_imports(node, filepath)
            self._check_dangerous_calls(node, filepath)
            self._check_env_access(node, filepath)

    def _check_imports(self, node, filepath):
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._flag_import(alias.name, filepath)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                self._flag_import(node.module, filepath)

    def _flag_import(self, module_name: str, filepath: Path):
        if any(dangerous in module_name for dangerous in self.DANGEROUS_IMPORTS):
            self.findings.append({
                'file': str(filepath),
                'type': 'dangerous_import',
                'severity': 'high',
                'message': f'Dangerous import: {module_name}'
            })
        elif any(net in module_name for net in self.NETWORK_IMPORTS):
            self.findings.append({
                'file': str(filepath),
                'type': 'network_import',
                'severity': 'medium',
                'message': f'Network import: {module_name}'
            })
        elif any(fs in module_name for fs in self.FILESYSTEM_IMPORTS):
            self.findings.append({
                'file': str(filepath),
                'type': 'filesystem_import',
                'severity': 'low',
                'message': f'Filesystem import: {module_name}'
            })

    def _check_dangerous_calls(self, node, filepath):
        if isinstance(node, ast.Call):
            func_name = self._get_func_name(node.func)
            if func_name in ['eval', 'exec', 'compile', '__import__']:
                self.findings.append({
                    'file': str(filepath),
                    'type': 'dangerous_call',
                    'severity': 'critical',
                    'message': f'Dangerous function call: {func_name}()'
                })

    def _check_env_access(self, node, filepath):
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute):
                if (isinstance(node.value.value, ast.Name) and
                    node.value.value.id == 'os' and
                    node.value.attr == 'environ'):
                    self.findings.append({
                        'file': str(filepath),
                        'type': 'env_access',
                        'severity': 'medium',
                        'message': 'Accesses environment variables'
                    })

    def _get_func_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ''

    def _calculate_risk_score(self):
        severity_weights = {
            'critical': 30,
            'high': 20,
            'medium': 10,
            'low': 5
        }

        for finding in self.findings:
            self.risk_score += severity_weights.get(finding['severity'], 0)

        self.risk_score = min(self.risk_score, 100)


def scan_mcp_server(repo_path: str) -> Dict:
    scanner = MCPSecurityScanner(repo_path)
    risk_score, findings = scanner.scan()

    if risk_score <= 25:
        recommendation = "AUTO-APPROVE"
    elif risk_score <= 50:
        recommendation = "REVIEW REQUIRED"
    elif risk_score <= 75:
        recommendation = "SANDBOX REQUIRED"
    else:
        recommendation = "BLOCK"

    return {
        'risk_score': risk_score,
        'recommendation': recommendation,
        'findings': findings,
        'total_issues': len(findings)
    }
