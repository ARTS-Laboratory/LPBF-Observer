import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
from sklearn.preprocessing import MinMaxScaler

# Read the CSV file
df = pd.read_csv('time_managment_data.csv')

# Update plot parameters
plt.rcParams.update({'image.cmap': 'viridis'})
cc = plt.rcParams['axes.prop_cycle'].by_key()['color']
plt.rcParams.update({
    'font.serif': ['Times New Roman', 'Times', 'DejaVu Serif', 'Bitstream Vera Serif',
                   'Computer Modern Roman', 'New Century Schoolbook', 'Century Schoolbook L',
                   'Utopia', 'ITC Bookman', 'Bookman', 'Nimbus Roman No9 L', 'Palatino',
                   'Charter', 'serif'],
    'font.family': 'serif',
    'font.size': 10,
    'mathtext.fontset': 'custom',
    'mathtext.rm': 'serif',
    'mathtext.it': 'serif:italic',
    'mathtext.bf': 'serif:bold',
    'axes.unicode_minus': True
})
plt.close('all')

# Change headers of columns
df.columns = ['TDS (ppm)', 'pH', 'turbidity', 'temperature', 'time']

# Drop time column
df.drop('time', axis=1, inplace=True)

# Normalize the data columns to range from -1 to 1
scaler = MinMaxScaler(feature_range=(-1, 1))
df_normalized = pd.DataFrame(scaler.fit_transform(df), columns=df.columns)

# Calculate the correlation matrix
correlation_matrix = df_normalized.corr()

# Set diagonal entries to NaN to make them blank in the heatmap
mask = np.eye(correlation_matrix.shape[0], dtype=bool)
correlation_matrix[mask] = np.nan

# Pre-format annotations with Unicode minus (U+2212)
annot_labels = correlation_matrix.applymap(
    lambda x: '' if pd.isna(x) else f"{x:.2f}".replace('-', '−')
)

# Create a custom colormap from tab orange to white to tab blue
tab_orange = plt.get_cmap('tab10')(1)  # tab:orange
tab_blue = plt.get_cmap('tab10')(0)    # tab:blue
custom_cmap = LinearSegmentedColormap.from_list("custom_cmap", [tab_orange, 'white', tab_blue])

# Plot the correlation matrix with KDE on the diagonal
fig, ax = plt.subplots(figsize=(4, 4), dpi=300)

# Create the dummy heatmap
sns.heatmap(correlation_matrix, annot=annot_labels, fmt="", cmap=custom_cmap, center=0, vmin=-1, vmax=1, square=True,
            cbar_kws={'label': 'pearson correlation coefficient', 'shrink': .80}, linewidths=0.5,
            annot_kws={"color": "black"}, mask=mask, ax=ax)
#remove gridlines
ax.grid(False)

# Ensure Unicode minus on colorbar ticks
cbar = ax.collections[0].colorbar
cbar.ax.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:g}".replace('-', '−')))

# Overlay the KDE plots
for i in range(correlation_matrix.shape[0]):
    ax_pos = ax.get_position()
    x0, y0, width, height = ax_pos.x0, ax_pos.y0, ax_pos.width, ax_pos.height
    factor = 1.0 / correlation_matrix.shape[0]

    # Adjust positions
    new_x = x0 + i * width * factor
    new_y = y0 + (correlation_matrix.shape[0] - 1 - i) * height * factor
    sub_ax = fig.add_axes([new_x, new_y, width * factor, height * factor])
   
    # KDE plot
    sns.kdeplot(df_normalized.iloc[:, i], ax=sub_ax, fill=True, color='skyblue')
    sub_ax.set_xlim(-1, 1)
    sub_ax.set_ylim(0, None)
    sub_ax.set_xlabel('')
    sub_ax.set_ylabel('')
    sub_ax.set_yticks([])
    sub_ax.set_xticks([])
    sub_ax.spines['top'].set_visible(False)
    sub_ax.spines['right'].set_visible(False)
    sub_ax.spines['left'].set_visible(False)
    sub_ax.spines['bottom'].set_visible(False)

# Adjust layout

# Save the figure
plt.savefig('correlation_matrix.png', dpi=300)
plt.savefig('correlation_matrix.svg')
plt.show()