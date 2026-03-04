"""
技能加载模块
实现渐进式技能加载：摘要始终在 System Prompt，always=true 技能全文注入，
其余由 LLM 按需通过 read_file 工具读取。

技能是全局固定的，存放在 ~/.quantmanus/skills/，不跟项目/workspace 走。
与 memory 和 sessions（跟项目走）区分开。

技能目录结构:
  ~/.quantmanus/skills/{skill-name}/SKILL.md

SKILL.md 格式:
  ---
  description: "技能描述"
  requires: '{"bins": ["pytest"], "env": ["API_KEY"]}'
  always: false
  ---

  # 技能内容...
"""
import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from xml.sax.saxutils import escape


class SkillsLoader:
    """
    技能加载器

    扫描全局技能目录（~/.quantmanus/skills/），
    提供技能列表、依赖检查、摘要构建和内容加载。
    技能是全局固定的，不跟项目/workspace 走。
    """

    def __init__(self, skills_dir: Path):
        """
        初始化技能加载器

        参数:
            skills_dir: 全局技能目录路径（如 ~/.quantmanus/skills/）
        """
        self.skills_dir = skills_dir

    def list_skills(self, filter_unavailable: bool = True) -> List[Dict]:
        """
        扫描全局技能目录，返回技能列表

        参数:
            filter_unavailable: 是否过滤掉不满足依赖的技能

        返回:
            技能信息字典列表，每项包含 name, path, source
        """
        skills = []

        if self.skills_dir.exists():
            for skill_dir in sorted(self.skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skills.append({
                            "name": skill_dir.name,
                            "path": str(skill_file),
                            "source": "global",
                        })

        if filter_unavailable:
            return [s for s in skills if self._check_requirements(
                self._parse_requires(self.get_skill_metadata(s["name"]))
            )]
        return skills

    def get_skill_metadata(self, name: str) -> Optional[Dict[str, str]]:
        """
        解析技能的 YAML frontmatter

        参数:
            name: 技能名称

        返回:
            frontmatter 键值对字典，无内容则返回 None
        """
        content = self.load_skill(name)
        if not content or not content.startswith("---"):
            return None

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None

        metadata = {}
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")
        return metadata

    def build_skills_summary(self) -> str:
        """
        生成 XML 格式的技能摘要，用于注入 System Prompt

        返回:
            XML 格式的技能列表字符串，无技能则返回空字符串
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""

        lines = ["<skills>"]
        for s in all_skills:
            meta = self.get_skill_metadata(s["name"]) or {}
            requires = self._parse_requires(meta)
            available = self._check_requirements(requires)

            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f'    <name>{escape(s["name"])}</name>')
            lines.append(f'    <description>{escape(self._get_skill_description(s["name"]))}</description>')
            lines.append(f'    <location>{escape(s["path"])}</location>')

            if not available:
                missing = self._get_missing_requirements(requires)
                if missing:
                    lines.append(f'    <requires>{escape(missing)}</requires>')

            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def get_always_skills(self) -> List[str]:
        """
        获取标记为 always=true 且满足依赖的技能名称列表

        返回:
            技能名称列表
        """
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            if meta.get("always", "").lower() == "true":
                result.append(s["name"])
        return result

    def load_skill(self, name: str) -> Optional[str]:
        """
        读取技能文件内容

        参数:
            name: 技能名称

        返回:
            技能文件内容字符串，不存在则返回 None
        """
        skill_file = self.skills_dir / name / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")

        return None

    def load_skills_for_context(self, skill_names: List[str]) -> str:
        """
        加载多个技能内容，去掉 frontmatter，用于注入 System Prompt

        参数:
            skill_names: 技能名称列表

        返回:
            拼接后的技能内容字符串
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                if content:
                    parts.append(f"### Skill: {name}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    # ====== 内部方法 ======

    @staticmethod
    def _check_requirements(requires: Dict) -> bool:
        """
        检查技能依赖是否满足

        参数:
            requires: 包含 bins 和 env 列表的字典

        返回:
            所有依赖是否都满足
        """
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False

        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False

        return True

    @staticmethod
    def _parse_requires(meta: Optional[Dict[str, str]]) -> Dict:
        """
        从 metadata 中解析 requires 字段为字典

        参数:
            meta: frontmatter 字典

        返回:
            包含 bins 和 env 列表的字典
        """
        if not meta:
            return {}
        raw = meta.get("requires", "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    def _get_skill_description(self, name: str) -> str:
        """
        从 metadata 中提取技能描述

        参数:
            name: 技能名称

        返回:
            描述字符串，无描述则返回空字符串
        """
        meta = self.get_skill_metadata(name)
        if meta:
            return meta.get("description", "")
        return ""

    @staticmethod
    def _get_missing_requirements(requires: Dict) -> str:
        """
        返回缺失依赖的描述字符串

        参数:
            requires: 包含 bins 和 env 列表的字典

        返回:
            格式化的缺失依赖描述
        """
        missing = []
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        """
        去除 YAML frontmatter

        参数:
            content: 原始文件内容

        返回:
            去除 frontmatter 后的内容
        """
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content
