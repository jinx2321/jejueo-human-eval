# Fixed evaluator group -> sentence assignment plan.
#
# Originally each group's slice was computed on the fly as a contiguous
# 1/NUM_GROUPS range per direction (see git history). That stopped working
# once group 0 needed to hold a specific, non-contiguous set of sentences:
# the ones the early "pilot" contributors (ckle man, kingkong, Jeju, korilla)
# had already rated, minus ckle man's sentences 133-149 (dropped for a
# rater-fatigue pattern - score spread across candidates collapsed from a
# mean of ~51 points to ~2 points and pacing roughly doubled starting there),
# padded out to a full 50 with random untouched sentences, plus 50 random
# ko2jj sentences to balance it to 100 total (50 per direction).
#
# The remaining 250 sentences per direction are split into 5 groups of 50
# each for new evaluators, constructed so that within every group the jj2ko
# and ko2jj sentence sets are disjoint (nobody rates the same underlying
# sentence pair in both directions) and, across all 6 groups, every sentence
# 0-299 is covered exactly once per direction. Built with random.seed(42);
# see scratchpad history for the generating script if this ever needs to be
# regenerated (e.g. group count changes again).

GROUP_SENTENCE_IDS = {
    0: {
        "jj2ko": [0, 13, 17, 45, 50, 51, 52, 53, 57, 62, 76, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 152, 163, 178, 200, 201, 256],
        "ko2jj": [2, 7, 8, 12, 23, 26, 27, 29, 34, 42, 43, 59, 65, 66, 69, 78, 82, 86, 97, 98, 99, 135, 140, 141, 151, 153, 159, 162, 175, 184, 186, 188, 190, 197, 203, 215, 227, 228, 232, 235, 243, 244, 255, 257, 272, 277, 282, 294, 297, 298],
    },
    1: {
        "jj2ko": [2, 4, 6, 7, 22, 25, 27, 29, 40, 41, 48, 56, 65, 71, 84, 90, 92, 93, 96, 97, 99, 135, 140, 148, 158, 160, 169, 170, 187, 191, 198, 215, 217, 244, 247, 252, 259, 260, 264, 265, 272, 281, 282, 284, 285, 288, 289, 292, 295, 299],
        "ko2jj": [9, 10, 11, 28, 46, 47, 49, 52, 54, 72, 74, 81, 85, 104, 113, 114, 119, 121, 123, 126, 130, 131, 137, 138, 143, 145, 152, 157, 161, 164, 171, 176, 183, 189, 193, 204, 222, 223, 229, 231, 241, 245, 258, 262, 263, 266, 269, 270, 286, 291],
    },
    2: {
        "jj2ko": [5, 10, 15, 18, 24, 34, 35, 36, 37, 46, 55, 60, 61, 67, 70, 75, 77, 81, 88, 89, 95, 133, 144, 151, 155, 159, 166, 171, 180, 186, 197, 202, 205, 219, 230, 231, 233, 234, 237, 248, 250, 251, 261, 267, 275, 278, 280, 290, 293, 297],
        "ko2jj": [4, 6, 20, 30, 32, 40, 41, 48, 53, 56, 57, 63, 73, 92, 96, 100, 103, 105, 107, 112, 116, 117, 118, 125, 132, 136, 147, 150, 168, 174, 179, 185, 196, 198, 209, 217, 218, 220, 242, 246, 247, 249, 264, 271, 276, 279, 281, 285, 288, 299],
    },
    3: {
        "jj2ko": [1, 3, 8, 11, 30, 32, 33, 49, 54, 59, 83, 86, 87, 98, 139, 143, 147, 149, 150, 156, 157, 167, 168, 174, 175, 177, 179, 181, 185, 188, 193, 195, 203, 208, 210, 222, 236, 240, 243, 253, 255, 257, 258, 266, 269, 274, 277, 286, 291, 298],
        "ko2jj": [0, 5, 13, 15, 17, 24, 31, 35, 36, 37, 38, 45, 55, 61, 67, 71, 80, 88, 89, 106, 108, 109, 111, 127, 134, 144, 158, 169, 180, 182, 194, 200, 201, 205, 211, 216, 226, 234, 238, 239, 248, 250, 254, 259, 261, 278, 280, 289, 290, 295],
    },
    4: {
        "jj2ko": [9, 14, 16, 19, 26, 31, 38, 39, 42, 43, 64, 73, 74, 78, 91, 94, 142, 145, 146, 153, 154, 162, 165, 172, 173, 176, 182, 184, 190, 192, 196, 199, 206, 213, 216, 221, 224, 226, 227, 232, 238, 239, 241, 242, 245, 249, 254, 283, 287, 294],
        "ko2jj": [1, 3, 21, 22, 33, 44, 58, 68, 75, 76, 77, 79, 83, 87, 90, 95, 110, 115, 122, 124, 128, 133, 139, 149, 155, 160, 167, 181, 187, 191, 195, 202, 207, 208, 212, 214, 225, 230, 233, 236, 251, 252, 253, 256, 260, 265, 268, 273, 274, 296],
    },
    5: {
        "jj2ko": [12, 20, 21, 23, 28, 44, 47, 58, 63, 66, 68, 69, 72, 79, 80, 82, 85, 134, 136, 137, 138, 141, 161, 164, 183, 189, 194, 204, 207, 209, 211, 212, 214, 218, 220, 223, 225, 228, 229, 235, 246, 262, 263, 268, 270, 271, 273, 276, 279, 296],
        "ko2jj": [14, 16, 18, 19, 25, 39, 50, 51, 60, 62, 64, 70, 84, 91, 93, 94, 101, 102, 120, 129, 142, 146, 148, 154, 156, 163, 165, 166, 170, 172, 173, 177, 178, 192, 199, 206, 210, 213, 219, 221, 224, 237, 240, 267, 275, 283, 284, 287, 292, 293],
    },
}

def sentence_ids_for_group(group_index, direction):
    return GROUP_SENTENCE_IDS.get(group_index, {}).get(direction, [])
