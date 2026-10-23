# %% imports
import pandas as pd
import matplotlib.pyplot as plt

# %% load data
packages_meta = pd.read_csv("../data/top_2500_depended_enriched.csv")
all_packages_runs = pd.read_csv("../data/full_dataset_decompression_energy_results.tsv", sep="\t")

all_packages_runs['TotalArchiveMB'] = all_packages_runs['TotalArchiveBytes'] / 1024
all_packages_runs['EnergyPerMB'] = all_packages_runs['EnergyKWh'] / all_packages_runs['TotalArchiveMB'] * 1000

# %% Descriptive stats

print(packages_meta.describe().to_string(float_format='{:.2f}'.format))
print(all_packages_runs[['Compressor', 'EnergyKWh', 'CPUConductedEnergyKWh', 'RAMConductedEnergyKWh', 'TotalElapsedMilliseconds', 'EnergyPerMB']].groupby('Compressor').describe())



# %% Plots of energy consumption

# Total Energy
plt.figure(figsize=(10, 6))
all_packages_runs.boxplot(
    column='EnergyKWh',
    by='Compressor',
    figsize=(10, 6),
    rot=30
)
plt.yscale('log')
plt.title('')
plt.suptitle('')
plt.xlabel('Compressor')
plt.ylabel('Energy (kWh)')
plt.tight_layout()
plt.show()

# CPU Energy
plt.figure(figsize=(10, 6))
all_packages_runs.boxplot(
    column='CPUConductedEnergyKWh',
    by='Compressor',
    figsize=(10, 6),
    rot=30
)
plt.yscale('log')
plt.title('')
plt.suptitle('')
plt.xlabel('Compressor')
plt.ylabel('CPU Energy (kWh)')
plt.tight_layout()
plt.show()

# RAM Energy
plt.figure(figsize=(10, 6))
all_packages_runs.boxplot(
    column='RAMConductedEnergyKWh',
    by='Compressor',
    figsize=(10, 6),
    rot=30
)
plt.yscale('log')
plt.title('')
plt.suptitle('')
plt.xlabel('Compressor')
plt.ylabel('RAM Energy (kWh)')
plt.tight_layout()
plt.show()


# Energy Per MB
plt.figure(figsize=(10, 6))
all_packages_runs.boxplot(
    column='EnergyPerMB',
    by='Compressor',
    figsize=(10, 6),
    rot=30
)
plt.yscale('log')
plt.title('')
plt.suptitle('')
plt.xlabel('Compressor')
plt.ylabel('Energy effiency (Wh/MB)')
plt.tight_layout()
plt.show()


# %% Violin plots
selected_columns = [
    'EnergyKWh',
    'CPUConductedEnergyKWh',
    'RAMConductedEnergyKWh',
    'TotalElapsedMilliseconds',
]

for column in selected_columns:
    groups = all_packages_runs.groupby('Compressor')

    plot_data = [
        group[column].dropna().values
        for _, group in groups
    ]

    labels = [
        compressor
        for compressor, _ in groups
    ]

    plt.figure(figsize=(10, 6))
    plt.violinplot(
        plot_data,
        showmeans=True,
        showmedians=True,
        showextrema=True,
    )

    plt.title(f'{column} by Compressor')
    plt.xlabel('Compressor')
    plt.ylabel(column)
    plt.xticks(
        ticks=range(1, len(labels) + 1),
        labels=labels,
        rotation=30,
        ha='right',
    )
    plt.tight_layout()
    plt.show()
# %%
