// File: knn.c

#include <math.h>
#include <stdlib.h>
#include <stdio.h>

/*
 * This C code is designed to be compiled into a shared library (.so or .dll)
 * and called from Python using the ctypes library. It provides a significant
 * speed-up for a K-Nearest Neighbors (KNN) search by leveraging C's performance
 * for looping and calculations.
 */

// Helper structure to keep track of a point's distance from the query point
// and its original index in the search array.
typedef struct {
    double distance;
    int index;
} DistanceIndex;

// A comparison function required by C's standard `qsort` function.
// It tells qsort how to compare two DistanceIndex structs so they can be
// sorted by their `distance` member in ascending order.
int compare_distance_index(const void *a, const void *b) {
    DistanceIndex *di_a = (DistanceIndex *)a;
    DistanceIndex *di_b = (DistanceIndex *)b;
    if (di_a->distance < di_b->distance) return -1;
    if (di_a->distance > di_b->distance) return 1;
    return 0;
}

// A helper function to calculate the squared Euclidean distance between two 2D points.
// Calculating the square root is computationally expensive, so we can often avoid it.
// By comparing squared distances, we get the same ordering of nearest neighbors
// without needing to perform a `sqrt` for every distance calculation.
double euclidean_distance_sq(double p1_x, double p1_y, double p2_x, double p2_y) {
    double dx = p1_x - p2_x;
    double dy = p1_y - p2_y;
    return dx * dx + dy * dy;
}


// The main KNN search function exposed to Python.
// It processes all query points in a single call to minimize Python-C overhead.
//
// Parameters:
//   - query_points: A pointer to a flat array of doubles representing the query points (e.g., [x1, y1, x2, y2, ...]).
//   - num_query_points: The number of points in the `query_points` array.
//   - search_points: A pointer to a flat array of doubles representing the points to search within.
//   - num_search_points: The number of points in the `search_points` array.
//   - k: The number of nearest neighbors to find for each query point.
//   - results: An output pointer to a flat integer array. The function will fill this array
//              with the *indices* of the k-nearest neighbors for each query point.
//              The size of this array must be `num_query_points * k`.
void knn_search(double* query_points, int num_query_points,
                double* search_points, int num_search_points,
                int k, int* results) {

    // This check is important. If k is larger than the number of points to search,
    // it's an impossible request.
    if (k > num_search_points) {
        fprintf(stderr, "Error: k cannot be greater than the number of search points.\\n");
        return;
    }

    // Allocate memory to store the distances for a *single* query point against all search points.
    // We can reuse this memory for each query point.
    DistanceIndex *distances = malloc(num_search_points * sizeof(DistanceIndex));
    if (distances == NULL) {
        fprintf(stderr, "Error: Failed to allocate memory for distances.\\n");
        return;
    }

    // --- Main Loop: Iterate over each query point ---
    for (int i = 0; i < num_query_points; i++) {
        // Each point has 2 coordinates (x, y), so we access them by `i * 2` and `i * 2 + 1`.
        double qp_x = query_points[i * 2];
        double qp_y = query_points[i * 2 + 1];

        // --- Inner Loop: Calculate distance to each search point ---
        for (int j = 0; j < num_search_points; j++) {
            double sp_x = search_points[j * 2];
            double sp_y = search_points[j * 2 + 1];

            distances[j].distance = euclidean_distance_sq(qp_x, qp_y, sp_x, sp_y);
            distances[j].index = j; // Store the original index
        }

        // Sort the `distances` array based on the distance. After this, the first
        // `k` elements will be the nearest neighbors.
        qsort(distances, num_search_points, sizeof(DistanceIndex), compare_distance_index);

        // --- Store Results: Extract the top k indices ---
        for (int ki = 0; ki < k; ki++) {
            // The `results` array is a flat 1D array. We calculate the correct
            // position to store the index for the i-th query point's k-th neighbor.
            results[i * k + ki] = distances[ki].index;
        }
    }

    // Free the allocated memory to prevent memory leaks.
    free(distances);
}
