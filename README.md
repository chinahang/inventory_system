# 台州海昌物流有限公司 - 进销存管理系统

> 本版本专为 **Windows 7 + Python 3.8** 环境优化

---

## 系统功能

- 首页仪表盘（采购趋势、库存状态、设备/人员领料图表）
- 采购单管理（物料模糊搜索、供应商联系方式、多物料明细、台账PDF/Excel）
- 领料单管理（物料/设备模糊搜索、移动加权均价自动填入、财务凭证PDF）
- 库存管理（实时库存、安全库存预警高亮、盘盈盘亏调整、PDF/Excel导出）
- 统计报表（按设备/人员统计，PDF/Excel导出）
- 操作日志（仅管理员可见，记录所有操作）
- 四角色权限（管理员/采购员/仓管员/普通操作员）

---

## Windows 7 安装步骤

### 第一步：安装 Python 3.8

前往 https://www.python.org/downloads/release/python-3810/ 下载
`python-3.8.10-amd64.exe`（64位）或 `python-3.8.10.exe`（32位）

安装时勾选 **"Add Python 3.8 to PATH"**

安装完成后打开命令提示符验证：
```
python --version
```
应显示 `Python 3.8.x`

### 第二步：安装依赖

打开命令提示符，进入系统目录：
```
cd C:\inventory_system
pip install -r requirements.txt
```

如果 pip 速度慢，可使用国内镜像：
```
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第三步：启动系统

```
cd C:\inventory_system
python main.py
```

看到以下输出说明启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 第四步：访问系统

打开浏览器（建议 Chrome），访问：
```
http://localhost:8000
```

默认账号：`admin` / `admin123`

---

## 开机自启动（可选）

创建批处理文件 `start.bat`：
```bat
@echo off
cd /d C:\inventory_system
python main.py
pause
```

将 `start.bat` 的快捷方式放入：
`C:\Users\用户名\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`

---

## PDF 中文支持

系统自动检测 Windows 字体，优先使用：
1. 微软雅黑（msyh.ttc）
2. 宋体（simsun.ttc）
3. 黑体（simhei.ttf）

Windows 7 默认已包含上述字体，**无需额外安装**。

---

## 数据备份

数据库文件为 `inventory.db`，位于系统目录下。
定期复制此文件到U盘或网络位置即可完成备份。

---

## 角色权限说明

| 功能 | 管理员 | 采购员 | 仓管员 | 普通操作员 |
|------|--------|--------|--------|------------|
| 新建采购单 | ✅ | ✅ | ❌ | ❌ |
| 采购台账查看 | ✅ | ✅ | ✅ | ✅ |
| 采购单删除 | ✅ | ❌ | ❌ | ❌ |
| 新建领料单 | ✅ | ❌ | ✅ | ❌ |
| 领料台账查看 | ✅ | ✅ | ✅ | ✅ |
| 领料单删除 | ✅ | ❌ | ❌ | ❌ |
| 库存管理查看 | ✅ | ✅ | ✅ | ✅ |
| 库存调整 | ✅ | ❌ | ✅ | ❌ |
| 统计报表 | ✅ | ✅ | ✅ | ✅ |
| 基础数据维护 | ✅ | ❌ | ❌ | ❌ |
| 操作日志 | ✅ | ❌ | ❌ | ❌ |

---

## 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.8.x | Win7最高支持版本 |
| FastAPI | 0.95.2 | Web框架 |
| Uvicorn | 0.22.0 | ASGI服务器 |
| SQLAlchemy | 1.4.49 | 数据库ORM |
| SQLite | 内置 | 数据存储 |
| ReportLab | 3.6.13 | PDF生成 |
| openpyxl | 3.1.2 | Excel生成 |
| Jinja2 | 3.1.2 | HTML模板 |
| bcrypt | 3.2.2 | 密码加密 |
