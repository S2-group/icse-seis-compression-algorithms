# %% imports
import pandas as pd
import matplotlib.pyplot as plt

# %% load data
zopfli_params = [15,30,45,60,75,90,100,200]
zopfli_base = "../data/zopfli_grid_search/zopfli_i{}_results.csv"
zopfli_results = []

# %%

for i in zopfli_params:
    file = zopfli_base.format(i)
    zopfli_results.append({ 'param': i, 'data': pd.read_csv(file)}) 

brotli_params = range(1,12)
brotli_base = "../data/brotli_grid_search/brotli_q{}_lgwin24_results.csv"
brotli_results = []

for i in brotli_params:
    file = brotli_base.format(i)
    brotli_results.append({ 'param': i, 'data': pd.read_csv(file)}) 

zstd_params = range(1,23)
zstd_base = "../data/zstd_grid_search/zstd_l{}_results.csv"
zstd_results = []

for i in zstd_params:
    file = zstd_base.format(i)
    zstd_results.append({ 'param': i, 'data': pd.read_csv(file)}) 

xz_params = range(1,10)
xz_base = "../data/xz_grid_search/xz_l{}_results.csv"
xz_results = []

for i in xz_params:
    file = xz_base.format(i)
    xz_results.append({ 'param': i, 'data': pd.read_csv(file)}) 

# %% extract data
zopfli_sizes, zopfli_times = [], []
for i, data in enumerate(zopfli_results):
    zopfli_sizes.append(data['data']['ZopfliMB'].sum())
    zopfli_times.append(data['data']['ElapsedMilliseconds'].median())

zstd_sizes, zstd_times = [], []
for i, data in enumerate(zstd_results):
    zstd_sizes.append(data['data']['ZstdMB'].sum())
    zstd_times.append(data['data']['ElapsedMilliseconds'].median())

brotli_sizes, brotli_times = [], []
for i, data in enumerate(brotli_results):
    brotli_sizes.append(data['data']['BrotliMB'].sum())
    brotli_times.append(data['data']['ElapsedMilliseconds'].median())

xz_sizes, xz_times = [], []
for i, data in enumerate(xz_results):
    xz_sizes.append(data['data']['XzMB'].sum())
    xz_times.append(data['data']['ElapsedMilliseconds'].median())

# %% Params

labels_size = 12
axes_size = 14

# %%
plt.figure(figsize=(8, 6))
plt.plot(zopfli_sizes, marker="o") 
plt.plot(zstd_sizes, marker="o")
plt.plot(brotli_sizes, marker="o")
plt.plot(xz_sizes, marker="o")

ax = plt.gca()
for label, size in zip(zopfli_params, zopfli_sizes):
    ax.text(
        zopfli_params.index(label),
        size,
        str(label),
        ha="center",
        va="top",
        fontsize=labels_size,
        clip_on=False,
    )
for label, size in zip(zstd_params, zstd_sizes):
    ax.text(
        zstd_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )
for label, size in zip(brotli_params, brotli_sizes):
    ax.text(
        brotli_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )
for label, size in zip(xz_params, xz_sizes):
    ax.text(
        xz_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )

plt.axhline(y=581.46, color='black', linestyle='dashed', linewidth=1)

plt.legend(["Zopfli", "Zstandard", "Brotli", "XZ"], loc='upper right', frameon=False, fontsize=axes_size)
plt.grid(True, alpha=0.3)
plt.xlabel("Configuration", size=axes_size)
plt.xticks(range(-1,22), labels=[])
plt.yticks([350, 400, 450, 500, 550, 600], size=axes_size)
plt.ylabel("Total dataset size (MB)", size=axes_size)
#plt.title("Median compressed archive size across grid-search configurations")
plt.savefig("sizes_plot_revised.pdf", bbox_inches="tight")

# %%
plt.figure(figsize=(8, 6))
plt.yscale("log")
plt.plot(zopfli_times, marker="o") 
plt.plot(zstd_times, marker="o")
plt.plot(brotli_times, marker="o")
plt.plot(xz_times, marker="o")

ax = plt.gca()
for label, size in zip(zopfli_params, zopfli_times):
    ax.text(
        zopfli_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )
for label, size in zip(zstd_params, zstd_times):
    ax.text(
        zstd_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )
for label, size in zip(brotli_params, brotli_times):
    ax.text(
        brotli_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )
for label, size in zip(xz_params, xz_times):
    ax.text(
        xz_params.index(label),
        size,
        str(label),
        ha="center",
        va="bottom",
        fontsize=labels_size,
        clip_on=False,
    )

plt.legend(["Zopfli", "Zstandard", "Brotli", "XZ"], loc='upper right', frameon=False, fontsize=axes_size)
plt.grid(True, alpha=0.3)
plt.xlabel("Configuration", size=axes_size)
plt.xticks(range(-1,22), labels=[])
plt.yticks([10, 100, 1000], size=axes_size)
plt.ylabel("Median compression time (ms)", size=axes_size)
#plt.title("Median compression times across grid-search configurations")

plt.savefig("times_plot_revised.pdf", bbox_inches="tight")

# %%
results = []
packages_size = [x for x in zip(zopfli_results[7]['data']['ZopfliBytes'], 
                                brotli_results[10]['data']['BrotliBytes'], 
                                xz_results[8]['data']['XzBytes'], 
                                zstd_results[21]['data']['ZstdBytes'])]

for t in packages_size:
    best = t.index(min(t))
    if best == 0:
        results.append("zopfli")
    elif best == 1:    
        results.append("brotli")
    elif best == 2:    
            results.append("xz")
    elif best == 3:    
            results.append("ztsd")

from collections import Counter

print(Counter(results).keys(), Counter(results).values())                

# %%
