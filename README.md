<div align="center">

# 🐝 Be-Humming

**Stop guessing your compression settings. This tool finds the _perfect_, perceptually-lossless size.**

</div>

<p align="center">
  <img alt="Python Version" src="https://img.shields.io/badge/python-3.8%2B-blue.svg?style=for-the-badge&logo=python">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge">
  <img alt="Code Style" src="https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge&logo=python">
  <img alt="Build" src="https://img.shields.io/badge/build-passing-brightgreen.svg?style=for-the-badge&logo=githubactions">
</p>

---

"Just _Save for Web_." "Run it through ImageOptim." "What `cwebp` quality are you using?"

We've all been there. You have a folder of high-res images, and you need them to be tiny for the web, but you _can't_ let them look like crusty, artifact-filled garbage.

**Be-Humming** is built on a simple idea: stop guessing. Instead of one "magic" setting, it's a **toolkit of four specialist algorithms** that use real perceptual metrics (like SSIM, PSNR, and Google's Butteraugli) to find the absolute smallest file size that _still looks perfect to the human eye_.

### Before vs. After (The "Hybrid" Strategy)

This isn't just about shrinking. It's about _intelligent_ shrinking.

| Original              | Be-Humming (Hybrid Perceptual)  |
| :-------------------- | :------------------------------ |
| `header.png` (4.8 MB) | `header.avif` (192 KB)          |
| `hero.jpg` (2.2 MB)   | `hero.webp` (215 KB)            |
| `promo.png` (819 KB)  | `promo.webp` (68 KB)            |
| **Total: 7.8 MB**     | **Total: 475 KB (94% Savings)** |

---

## ⚙️ Installation

This is a professional tool, so installation has two parts. First, our code. Second, the powerful command-line binaries that do the heavy lifting.

### 1. The Easy Part: This Repo

`Be-Humming` is a Python package. You can install it right from this repo.

```bash
# 1. Clone the repository
git clone https://github.com/your-username/be-humming.git
cd be-humming

# 2. Install the package and its dependencies
# The -e flag (editable) means you can change the code and not have to re-install.
pip install -e .
```

You can now run `be-humming --version` from anywhere on your system.

### 2\. The Real Deal: The Binaries

This tool is a "wrapper" that intelligently controls the best compression tools on the planet. **You must install them yourself.**

| Tool            | Ubuntu / Debian (`apt`)         | macOS (`brew`)             | Why?                           |
| :-------------- | :------------------------------ | :------------------------- | :----------------------------- |
| **MozJPEG**     | `sudo apt install mozjpeg`      | `brew install mozjpeg`     | The gold standard for JPEGs.   |
| **WebP**        | `sudo apt install webp`         | `brew install webp`        | Next-gen format from Google.   |
| **AVIF**        | `sudo apt install libavif-apps` | `brew install avif`        | The _newest_ next-gen format.  |
| **Oxipng**      | `sudo apt install oxipng`       | `brew install oxipng`      | Best-in-class lossless PNG.    |
| **Zopfli**      | `sudo apt install zopfli`       | `brew install zopfli`      | Best _compression_ (but slow). |
| **Butteraugli** | (Manual install)                | `brew install butteraugli` | Google's perceptual metric.    |

**Heads up:** If you skip a tool (e.g., `avifenc`), Be-Humming will just warn you and skip that format. No crashes.

---

## 🚀 How to Use It

The main tool is `be-humming`. You give it global options (like `--input`) and then tell it which **strategy** to use.

Get a full list of commands by running `help`:

```bash
be-humming --help
```

### Global Options

These work for _all_ strategies:

- `-i`, `--input` **(Required)**: The folder of images to process.
- `-o`, `--output` **(Required)**: The folder where results will be saved.
- `-w`, `--workers`: Number of parallel jobs to run. (Default: all your CPU cores)
- `--report-json`: Save a `report.json` of all results.
- `--report-csv`: Save a `report.csv` of all results.

### The Strategies (The Main Event)

This is the fun part. You don't just "compress"—you pick your _philosophy_.

#### 1\. `perceptual-best-of` (The Sprinter)

- **What it does:** Zips through your images, creates a JPEG, WebP, and AVIF for each, and picks the **absolute smallest file** that passes a basic SSIM quality check.
- **Best for:** A quick, "good-enough" pass on a folder of mixed images.
- **Run it:**
  ```bash
  be-humming -i ./raw-images -o ./public \
    perceptual-best-of \
    --ssim 0.98 \
    --resize 2560
  ```

#### 2\. `lossless-first` (The Perfectionist)

- **What it does:** Tries _everything_ to get a **pixel-perfect** lossless compression (`oxipng`, `zopflipng`, `webp --lossless`). It will _only_ do a lossy conversion if you force it with `--target-kb`.
- **Best for:** Optimizing PNG assets (logos, icons, UI elements) where you _cannot_ lose quality.
- **Run it:**
  ```bash
  # Optimize all PNGs, but if any are still over 200KB,
  # create a lossy WebP instead.
  be-humming -i ./png-assets -o ./optimized-assets \
    lossless-first \
    --target-kb 200
  ```

#### 3\. `jpeg-binary-search` (The Specialist)

- **What it does:** This is a JPEG surgeon. It uses a **binary search** to find the _absolute lowest_ JPEG quality (e.g., Q=68) that still passes a strict PSNR/SSIM check. It uses the `Pillow` encoder, so it's fast and has few dependencies.
- **Best for:** Processing a huge library of JPEGs (like product photos) to a consistent _perceptual_ quality.
- **Run it:**
  ```bash
  be-humming -i ./hi-res-photos -o ./web-jpegs \
    jpeg-binary-search \
    --use-ssim \
    --target-ssim 0.995
  ```

#### 4\. `hybrid-perceptual` (The Juggernaut)

- **What it does:** This is the 'gloves-off' strategy. It's slow, but the results are unmatched. It performs a **binary search for _each format_** (JPEG, WebP, _and_ AVIF) using the most advanced metrics (like Butteraugli) and _then_ picks the smallest of those.
- **Best for:** Your final production build step. When you absolutely, positively need the smallest possible asset that looks _perfect_.
- **Run it:**

  ```bash

  # A score < 1.0 is considered "perceptually lossless".
  be-humming -i ./source-files -o ./final-delivery \
    hybrid-perceptual \
    --use-butter \
    --target-butter 1.0
  ```

---

## 🧠 Deep Dive: How the Strategies Compare

| Strategy                 | Philosophy                 | Speed        | Use Case                 | Metrics Used                |
| :----------------------- | :------------------------- | :----------- | :----------------------- | :-------------------------- |
| **`perceptual-best-of`** | "Smallest file wins"       | ⚡️ Fast     | Quick pass on web assets | SSIM (OpenCV)               |
| **`lossless-first`**     | "Pixel-perfect or bust"    | 🐢 Slow      | UI assets, logos, icons  | Pixel-for-pixel diff        |
| **`jpeg-binary-search`** | "Surgical JPEG specialist" | 💨 Medium    | JPEG photo libraries     | SSIM (skimage), PSNR        |
| **`hybrid-perceptual`**  | "Best of all worlds"       | 💀 Very Slow | Final build/delivery     | **Butteraugli**, SSIM, PSNR |

---

## 🏗️ Project Structure

This project is structured as a proper Python package. This makes it scalable, maintainable, and easy to test.

```
/Be-Humming
├── .gitignore
├── README.md
├── requirements.txt          <-- All the `pip` dependencies
├── pyproject.toml            <-- This makes the `be-humming` command
│
└── /be_humming               <-- The main source code package
    ├── __init__.py           <-- Makes `be_humming` a package
    ├── main.py               <-- The CLI "conductor" (argparse)
    │
    ├── /mods           <-- Each "Algoritham" lives here
    │   ├── __init__.py
    │   ├── perceptual.py
    │   ├── lossless.py
    │   ├── jpeg_binary_search.py
    │   └── hybrid_perceptual.py
    │
    └── /utils                <-- All the shared, boring code
        ├── __init__.py
        ├── image_ops.py      <-- All resizing functions
        ├── logging.py        <-- The pretty console `Log` class
        ├── metrics.py        <-- SSIM, PSNR, Butteraugli logic
        ├── reporting.py      <-- JSON/CSV report writers
        └── shell.py          <-- The master `run_cmd` function
```

---

## 🤝 Contributing

This is for all the developers like me who have to deal with lots of images, Hope this tools helps.
