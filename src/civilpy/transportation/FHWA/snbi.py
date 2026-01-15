#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import matplotlib.pyplot as plt

# Data for 7 pie charts, one for each section
data = [[15, 3, 3], [0, 11, 11], [10, 2, 4], [25, 7, 3],
        [4, 1, 9], [2, 3, 11], [10, 7, 6]]

labels = ['C', 'P', 'D']  # Clean, Partial, Difficult,

titles = [
    'Bridge Identification',
    'Bridge Material and Type',
    'Bridge Geometry',
    'Features',
    'Loads, Load Rating and Posting',
    'Inspections',
    'Bridge Condition'
]

no_fields = [
    '21', '22', '16', '35', '14', '16', '23'
]

# Softer pastel colors for the pie charts
colors = ['#66BB6A', '#FFEE58', '#EF5350']  # Material green, red, and yellow

# Create subplots (2 rows: 3 on the top, 4 on the bottom)
fig, axes = plt.subplots(2, 4, figsize=(12, 6))

# Flatten axes array and loop over data to create each pie chart
for i, ax in enumerate(axes.flat):
    if i < len(data):
        ax.pie(
            data[i],
            labels=labels,
            autopct='%1.1f%%',
            colors=colors  # Set softer colors
        )
        ax.set_title(f"Section {i+1}: {no_fields[i]}")
        ax.text(0, -1.2, f"{titles[i]}", fontsize=9, va='center', ha='center')  # Subtitle below
    else:
        ax.axis('off')  # Hide unused subplot axes

snbi_data_crosswalk = plt
