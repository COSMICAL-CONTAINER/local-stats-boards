# -*- coding: utf-8 -*-
"""核心渲染器：把 DATA(JSON) + BOARD 配置(JS) 注入骨架模板，输出单文件看板 HTML。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _echarts_path():
    return os.path.join(HERE, "echarts.min.js")


def render_board(board_title: str, board_logo: str, data_json: str, config_js: str) -> str:
    """注入占位符并返回完整 HTML 字符串。只读不写，stdout 由调用方输出。"""
    tpl = (_read(os.path.join(HERE, "base_template.html"))
           .replace("__BOARD_TITLE__", board_title)
           .replace("__BOARD_LOGO__", board_logo))
    return (tpl
            .replace("__ECHARTS_JS__", _read(_echarts_path()))
            .replace("__CHARTS_JS__", _read(os.path.join(HERE, "charts.js")))
            .replace("__DATA_JSON__", data_json)
            .replace("__BOARD_CONFIG_JS__", config_js))
