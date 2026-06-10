# python-docx 中文专利报告生成参考

## 关键代码片段

### 表格边框

```python
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

def set_cell_border(cell, **kwargs):
    """Set cell border. Usage: set_cell_border(cell, top={"sz": 4, "color": "999999"}, ...)"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}></w:tcBorders>')
    for edge, attrs in kwargs.items():
        element = parse_xml(
            f'<w:{edge} {nsdecls("w")} w:val="{attrs.get("val", "single")}" '
            f'w:sz="{attrs.get("sz", 4)}" w:space="0" '
            f'w:color="{attrs.get("color", "000000")}"/>'
        )
        tcBorders.append(element)
    tcPr.append(tcBorders)
```

### 中文字体设置

每个 run 必须同时设置西文和中文字体：

```python
run.font.name = 'Microsoft YaHei'
run.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
```

### 表头底色

```python
shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="2B579A" w:val="clear"/>')
cell._tc.get_or_add_tcPr().append(shading)
```

### 页面设置

```python
from docx.shared import Cm
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
```

## 避坑清单

1. **不要用 pandoc 生成带表格的报告** → 表格无边框
2. **不要用 docx-js 生成中文报告** → 书名号/引号触发 JS 语法错误
3. **python-docx 是首选** → `import docx`，不是 `python-docx`
4. **完成立即交付** → 生成后立即把 .docx 交付给用户，不留本地路径让用户自己取（交付通道由运行环境决定）
