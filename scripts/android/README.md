# Android wheel tooling

两个脚本,都来自 `python-android-apk` skill,原样搬进仓库 —— **CI 跑得到的
只有仓库里的文件**,skill 装在开发者本机上,workflow 看不见它。

| 文件 | 作用 |
|---|---|
| `android_wheel.py` | 把 `src/padpd/` 里指定的模块 cython 化,交叉编译成 Android `.so`,打成一个按 ABI 打标签的 wheel |
| `inspect_apk.py` | 走进 APK 里 Chaquopy 的 payload 压缩包,报告每个包是源码还是原生;`--native` / `--pure` 把这件事变成断言 |

## 相对上游的改动

只有一处:`android_wheel.py` 增加了 `--strip-requires`。

`pyproject.toml` 声明 `numpy>=1.24`、`scipy>=1.10`、`matplotlib>=3.7`;
Android 这边**故意**装 `numpy==1.23.3` + `scipy==1.8.1`(Chaquopy 的仓库只
有到这里,理由写在 `android/app/build.gradle` 的 pip 块里),matplotlib 干脆
不装。把 `Requires-Dist` 留在 wheel 的 METADATA 里,pip 会重新去解一遍这场
已经做过的决定,然后失败。这个选项只删 `Requires-Dist` 那几行,名字、版本、
许可证仍然来自 `pyproject.toml`,不会出现第二份、会漂移的元数据。

## 怎么用

```bash
pip install "cython>=3.0" build

# 每个要打包的 ABI 一个 wheel
python scripts/android/android_wheel.py --package padpd --compile all \
    --abi arm64-v8a --ndk "$ANDROID_NDK_HOME" \
    --target-version 3.10.15-0 --strip-requires

cd android && ./gradlew :app:assembleRelease -PpadpdCompiled=true
```

`--target-version 3.10.15-0` 不是猜的:Chaquopy 16.0.0 的
`com/chaquo/python/internal/Common.class` 里 `PYTHON_VERSIONS` 把 `3.10`
映射到 `3.10.15`,build number 是 `0`。Maven Central 上 `3.10.15-1` 也存在,
但 Chaquopy 要的是 `-0`。换 Chaquopy 版本时重新读一遍那张表,或者按 skill
说的看一眼 `~/.gradle/caches/modules-2/files-2.1/com.chaquo.python/target/`。

不带 `--abi`、改用 `--host` 会用本机编译器走完全一样的流程,不需要 NDK——
这是本地验证「编译完测试还过不过」的办法,`android-compiled.yml` 就是这么
用的。

## 它买到了什么,没买到什么

抬高的是**读算法**的成本:从「解压就能看」变成「得反汇编」。除此之外:

- 没编译的模块照旧是字节码,`strings` 能拿回函数名、行号、整段 docstring。
  本仓库当前只编译 `src/padpd/`;`gui_core/`、`padpd_mobile/`、`manual/`、
  `examples/` 仍是明文,理由见 `android/README.md`。
- **字面常量编译后仍在**,躺在常量池里,一次精确搜索就能命中。
- 运行时能拿到的东西就能拿到 —— APP 界面上显示的任何数值都不受影响。

它不是授权校验,不是数据保护,也不是对界面内容的混淆。
