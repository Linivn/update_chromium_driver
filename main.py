import datetime
import os
import platform
import re
import subprocess
import zipfile
from pathlib import Path

import requests


def decode_str(res):
    result = res
    if type(result) is bytes:
        result = result.decode("gbk", errors="ignore")
    else:
        result = str(result)
    return result.encode("utf-8").decode("utf-8", errors="ignore")


def run(command, desc=None, errdesc=None, isWait=True, **kwargs):
    if desc is not None:
        pass

    if not os.path.exists("./logs"):
        os.mkdir("./logs")

    logfile = f'./logs/output_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.txt'

    popen = subprocess.run if isWait else subprocess.Popen
    result = popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE if isWait else open(logfile, "w"),
        stderr=subprocess.PIPE,
        shell=True,
        **kwargs,
    )

    result.decode_stdout = ""

    if not isWait:
        result.logfile = logfile

        return result

    decode_stdout = decode_str(result.stdout) if len(result.stdout) else None
    decode_stderr = decode_str(result.stderr) if len(result.stderr) else None

    if result.returncode != 0:
        message = f"{errdesc or 'Error running command'}.\nCommand: {command}\nErrorCode: {result.returncode}\nStdout: {decode_stdout or '<empty>'}\nStderr: {decode_stderr or '<empty>'}"
        raise RuntimeError(message)

    result.decode_stdout = decode_stdout
    return result


def save_file(path, content, mode="w", encoding="utf-8"):
    path = Path(path).as_posix()
    path_arr = path.split("/")
    path_arr.pop()
    dir_path = "/".join(path_arr)
    if len(path_arr) > 1 and (not os.path.exists(Path(dir_path))):
        # 目录不存在则创建
        os.makedirs(Path(dir_path))
    if mode == "wb":
        encoding = None
    with open(path, mode=mode, encoding=encoding) as f:
        f.write(content)


def get_browser_version(data):
    try:
        if platform_txt == "win32":
            # win32 通过注册表查询版本信息: HKEY_CURRENT_USER\SOFTWARE\[Google\Chrome|Microsoft\Edge]\BLBeacon: version
            import winreg

            key_path = f"SOFTWARE\\{data}\\BLBeacon"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            value = winreg.QueryValueEx(key, "version")[0]
        else:
            # 其他 通过命令行获取版本信息
            run_res = run(data)
            res_text = run_res.decode_stdout if run_res else ""
            find_res = re.findall(version_re, res_text)
            version_res = list(find_res[0] if find_res else ())
            value = version_res[0] if version_res else "0.0.0.0"

        print("Browser version: ", value, data)
        if value:
            return value
        else:
            raise RuntimeError(f'get_browser_version error, error: {value}')
    except BaseException as e:
        print("Error get_browser_version: ", e)
        return "0.0.0.0"  # 没有安装Chromium内核浏览器


def update_latest_driver(browser_version):
    if browser_version == '0.0.0.0':
        raise RuntimeError(
            f'The current system may not have {browser_target} browser installed, please check if it is installed')

    print(f"Update [{browser_target}] web driver start.")
    platform_driver = get_platform()
    if browser_target == "chrome":
        short_version = browser_version.split(".")[0:1]
        latest_version = requests.get(
            f'{base_url}/LATEST_RELEASE_{".".join(short_version)}'
        ).text
        download_url = f"{base_url}/{latest_version}/chromedriver_{platform_driver}.zip"
    else:
        # https://msedgedriver.azureedge.net/98.0.1108.56/edgedriver_win64.zip
        latest_version = browser_version
        download_url = f"https://msedgedriver.azureedge.net/{latest_version}/edgedriver_{platform_driver}.zip"

    latest_version_file = f"{default_driver_path}/LATEST_VERSION.txt"
    is_current_latest = False  # 判断driver是否为最新版本
    try:
        # with open(latest_version_file) as f:
        #     if latest_version == f.read().strip():
        #         is_current_latest = True
        target_driver_path = Path(f'{default_driver_path}/{browser_target}driver')
        if platform_txt != 'win32':
            run(f'chmod +x {target_driver_path}')

        latest_version_res = run(f'"{target_driver_path}" --version')
        if latest_version_res.decode_stdout and latest_version in latest_version_res.decode_stdout:
            is_current_latest = True

    except BaseException as e:
        # print(e)
        pass

    if not is_current_latest:
        print(
            f"Download web driver info: browser_version is {browser_version}, driver_version is {latest_version}, download_url is {download_url}"
        )
        # 下载 driver zip文件
        response = requests.get(
            download_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
            },
        )
        local_file = Path(f"{default_driver_path}/driver.zip")
        save_file(local_file, response.content, mode="wb")
        print("Download web driver zip file: ", response.status_code, download_url)
        # with open(local_file, 'wb') as zip_file:
        #       zip_file.write(response.content)

        # 解压缩zip文件
        f = zipfile.ZipFile(local_file, "r")
        for file in f.namelist():
            # print(file, default_driver_path)
            f.extract(file, f"{default_driver_path}")
        f.close()
        # f.unlink()  # 解压缩完成后删除zip文件
        run(f'{"del" if platform_txt == "win32" else "rm -rf"} {local_file}')
        save_file(latest_version_file, latest_version, mode="w")  # 保存最新版本号

    print(
        f"Update [{browser_target}] web driver done. Driver latest version: {latest_version}. {'Current local version is already the latest version and does not need to be updated.' if is_current_latest else ''}\nWeb driver path: {default_driver_path}"
    )


def get_platform():
    platform_str = platform.platform().lower()

    if "windows" in platform_str:
        return "win32"
    if "linux" in platform_str:
        return "linux64"
    if "macos" in platform_str:
        return "mac64"

    raise RuntimeError(f"Current platform [{platform_str}] is unknown or not supported")


if __name__ == "__main__":
    argvs = os.sys.argv
    browser_target = ""
    if len(argvs) > 1:
        browser_target = os.sys.argv[1] or None

    if not browser_target:
        browser_target = "chrome"

    if browser_target not in ["chrome", "msedge"]:
        raise ValueError(
            "Browser target is only allowed when entering ['chrome','msedge']"
        )

    platform_txt = get_platform()

    temp_path = Path(
        (os.getenv("TEMP") if platform_txt == "win32" else "/tmp") or "./tmp"
    )  # temp目录
    default_driver_path = Path(f"{temp_path}/browser_driver/{browser_target}")
    base_url = (
        "https://registry.npmmirror.com/-/binary/chromedriver"  # Chromium driver 国内镜像网站
    )
    version_re = re.compile(r"([1-9]\d*(\.\d+){3})")  # 匹配前4位版本信息

    if platform_txt == "win32":
        browser_map = {"chrome": "Google\\Chrome", "msedge": "Microsoft\\Edge"}
    elif platform_txt == "mac64":
        browser_map = {
            "chrome": "/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version",
            "msedge": "/Applications/Microsoft\ Edge.app/Contents/MacOS/Microsoft\ Edge --version",
        }
    else:
        browser_map = {
            "chrome": "google-chrome --version",
            "msedge": "microsoft-edge --version",
        }

    update_latest_driver(get_browser_version(browser_map.get(browser_target)))
