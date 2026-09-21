# Fixed evaluator group -> sentence assignment plan.
#
# Originally each group's slice was computed on the fly as a contiguous
# 1/NUM_GROUPS range per direction (see git history). That stopped working
# once group 0 needed to hold a specific, non-contiguous set of sentences:
# the ones the early "pilot" contributors (ckle man, kingkong, Jeju, korilla)
# had already rated, minus ckle man's sentences 133-149 (dropped for a
# rater-fatigue pattern - score spread across candidates collapsed from a
# mean of ~51 points to ~2 points and pacing roughly doubled starting there).
#
# Rebalanced a second time (2026-09-18) after a still-unresolved bug let a
# brand-new evaluator's first connection see all 300 sentences unrestricted
# (self-correcting on reconnect), which let "noiznoiz" (group 4) rate far
# beyond their own 50/50 slice - including some stray touches inside groups
# 0/1/2/3's territory - and separately produced a duplicate identity,
# "noiznoiz17", for the same real person. This rebalance:
#   - fixes group 4's definition to noiznoiz's full actual work (88 jj2ko +
#     50 ko2jj, with 6 sentences rated in both directions - an accepted,
#     already-happened duplicate from the bug, not fixable after the fact)
#   - scrubs every sentence noiznoiz touched out of every other group's
#     future-assignable list, so nobody is ever asked to re-rate them
#   - gives "noiznoiz17" a group of its own (group 5) built entirely from
#     sentences nobody has touched, since the user's plan is to treat it as
#     a fresh identity for the same person to keep working under
#   - preserves every other real evaluator's already-done work (pilot's 40
#     jj2ko, g's 1, ddudu's 1) inside their own group
#   - sentence 239 (jj2ko) is deliberately excluded from every group at the
#     user's request; a handful of other sentences also don't appear in any
#     group's jj2ko/ko2jj list because they were only ever touched by a
#     stray bug-artifact rating from a non-owner (e.g. sentence 2 was rated
#     by "ddudu" - group 3's owner - but sentence 2 belongs to group 1's
#     territory, so it's retired rather than handed to test1 as "fresh")
#
# Because group 4 grew from its original 50 jj2ko sentences to 88, there
# is a hard shortfall: 300 total - group4's 88 leaves only 212 for the
# other 5 groups to share, not 250 (5 x 50). Per an explicit choice (user
# confirmed, "B안": prioritize groups 1/2/3 reaching their full 50/50 over
# group 5), groups 1/2/3 were topped up to 50/50 first from the pool of
# untouched sentences shared across groups 1/2/3/5, leaving group 5
# ("noiznoiz17") with only 16 jj2ko + 47 ko2jj for now. The plan is to hand
# noiznoiz17 a fresh additional 100 later if they want to keep going, once
# groups 1/2/3 actually have active evaluators using their slices.
#
# Sentences 0, 1 and 5 (jj2ko) are each rated by two identities: they were
# already someone's legitimate real work (pilot's 0, ddudu's 1, g's 5)
# before noiznoiz separately, accidentally rated them too during the bug.
# Since that duplication already happened and can't be un-rated, and no
# *new* evaluator will ever see those sentences again (they stay inside
# their real owner's closed group), they're kept where the real work is.
#
# Built with random.seed(11) against a 2026-09-18 production data export;
# see scratchpad history in that session for the generating script if this
# ever needs to be regenerated.
#
# 2026-09-21: by this point almost the entire 300-sentence corpus was
# already touched or claimed by some group (only ~1 genuinely free sentence
# left anywhere), so a brand new evaluator ("chloe") got auto-routed to
# group 5 by the least-loaded-group logic - whose sentences had, in the
# meantime, already been fully rated by noiznoiz17 before their group1/5
# swap. She unknowingly duplicated 9 of them before this was caught. Rather
# than throw that away, group 3 (ddudu's slot - inactive since 2026-09-16,
# never completed a single sentence) was handed to her instead: her 9
# already-rated sentences stay put, and the rest of group 3's untouched
# territory fills in around them. That alone landed short of a full 50/50
# (7 of her 9 already-rated jj2ko sentences happen to numerically coincide
# with what would have been group 3's ko2jj list, and 2 similarly collided
# on the jj2ko side too), with no spare, unclaimed territory left anywhere
# else in the corpus to make up the difference - so the user chose to close
# the gap by lending group 3 a handful of sentences (7 ko2jj + 2 jj2ko)
# carved out of group 2 (g)'s own untouched territory instead, since g has
# been just as inactive as ddudu. Group 2 now sits at 48 jj2ko / 43 ko2jj
# rather than 50/50 as a result - the same kind of trade made for group 5
# earlier, just smaller and paid by a different idle group.
#
# 2026-09-21 (later same day): clarified that g and chloe are the only two
# real active evaluators right now - pilot and test1 are placeholders with
# no dedicated person behind them (test1 never rated anything at all; ddudu
# turned out not to be a protected identity either, despite group 3 having
# briefly been treated as if it might need protecting for them). So:
#   - group 2 (g) was topped up from 48/43 to a full 50/50 by borrowing
#     pilot's still-untouched territory (2 jj2ko + 7 ko2jj) - NOT test1's,
#     since test1's entire slice is already fully rated by noiznoiz17 and
#     handing it to g would just mean duplicate work, same trap chloe fell
#     into with group 5.
#   - pilot's remaining territory, test1's old (fully-rated) slice, and
#     ddudu's handful of stray touches are all merged into one shared
#     "already evaluated / not an active assignment" bucket, used for BOTH
#     group 0 and group 5 (so pilot and test1 - whichever logs in - see the
#     same thing). It isn't a clean disjoint-from-itself 50/50 slice and
#     isn't meant to be: nobody is actively working through it, it just
#     exists so its sentences are never handed to g/chloe/noiznoiz17 as
#     "fresh." A few sentences it contains (e.g. 2) are also already
#     covered by group 4 (noiznoiz) for the same reason - harmless
#     redundancy between two non-active record-keeping groups.

GROUP_SENTENCE_IDS = {
    0: {
        "jj2ko": [0, 1, 2, 50, 51, 52, 53, 57, 62, 67, 86, 93, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 136, 138, 152, 158, 174, 178, 185, 191, 194, 200, 201, 210, 217, 252, 256, 276, 284, 286],
        "ko2jj": [5, 7, 8, 10, 12, 15, 23, 26, 27, 28, 29, 34, 42, 47, 59, 63, 65, 66, 78, 80, 82, 89, 91, 97, 99, 135, 141, 142, 143, 151, 159, 161, 162, 163, 164, 165, 169, 175, 179, 182, 184, 186, 188, 190, 197, 203, 204, 211, 215, 220, 227, 228, 232, 235, 238, 239, 243, 244, 248, 250, 257, 262, 267, 270, 272, 275, 277, 282, 290, 291, 293, 294, 297],
    },
    1: {
        "jj2ko": [49, 54, 55, 61, 63, 65, 66, 68, 69, 72, 77, 83, 87, 88, 89, 95, 99, 135, 137, 140, 141, 149, 150, 151, 156, 157, 164, 167, 175, 187, 188, 189, 204, 214, 215, 220, 236, 237, 248, 251, 257, 262, 267, 273, 277, 278, 280, 281, 282, 291],
        "ko2jj": [4, 6, 13, 17, 19, 30, 31, 38, 40, 41, 56, 62, 73, 74, 81, 96, 101, 117, 119, 127, 154, 170, 172, 173, 177, 178, 180, 193, 198, 199, 200, 205, 209, 218, 226, 229, 231, 234, 240, 242, 246, 247, 254, 258, 271, 284, 288, 289, 292, 299],
    },
    2: {
        "jj2ko": [5, 71, 76, 79, 81, 84, 85, 90, 92, 96, 97, 133, 134, 139, 143, 163, 166, 168, 169, 170, 171, 177, 180, 183, 197, 203, 205, 208, 209, 218, 222, 228, 229, 233, 240, 243, 244, 246, 250, 253, 258, 260, 265, 268, 285, 288, 290, 293, 295, 296],
        "ko2jj": [9, 32, 36, 37, 43, 46, 54, 61, 64, 69, 70, 72, 88, 94, 98, 103, 105, 106, 107, 108, 113, 116, 137, 140, 144, 147, 148, 150, 153, 157, 158, 192, 201, 213, 216, 219, 223, 224, 245, 255, 259, 261, 263, 264, 269, 279, 280, 281, 287, 298],
    },
    3: {
        "jj2ko": [56, 59, 67, 82, 86, 93, 98, 136, 138, 144, 147, 148, 155, 158, 159, 160, 161, 174, 179, 181, 186, 193, 195, 198, 202, 207, 211, 212, 217, 219, 223, 225, 234, 247, 255, 261, 263, 264, 269, 270, 271, 272, 274, 275, 279, 286, 289, 292, 297, 299],
        "ko2jj": [0, 11, 20, 24, 25, 35, 39, 45, 48, 49, 55, 57, 60, 71, 84, 85, 92, 100, 109, 114, 118, 120, 125, 130, 134, 145, 146, 156, 166, 168, 171, 176, 183, 185, 189, 194, 196, 206, 210, 221, 222, 237, 241, 249, 266, 276, 278, 283, 285, 295],
    },
    4: {
        "jj2ko": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 64, 73, 74, 78, 91, 94, 142, 145, 146, 153, 154, 162, 165, 172, 173, 176, 182, 184, 190, 192, 196, 199, 206, 213, 216, 221, 224, 226, 227, 232, 238, 241, 242, 245, 249, 254, 283, 287, 294],
        "ko2jj": [1, 3, 21, 22, 33, 44, 58, 68, 75, 76, 77, 79, 83, 87, 90, 95, 110, 115, 122, 124, 128, 133, 139, 149, 155, 160, 167, 181, 187, 191, 195, 202, 207, 208, 212, 214, 225, 230, 233, 236, 251, 252, 253, 256, 260, 265, 268, 273, 274, 296],
    },
    5: {
        # identical to group 0 - see the 2026-09-21 note above.
        "jj2ko": [0, 1, 2, 50, 51, 52, 53, 57, 62, 67, 86, 93, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 136, 138, 152, 158, 174, 178, 185, 191, 194, 200, 201, 210, 217, 252, 256, 276, 284, 286],
        "ko2jj": [5, 7, 8, 10, 12, 15, 23, 26, 27, 28, 29, 34, 42, 47, 59, 63, 65, 66, 78, 80, 82, 89, 91, 97, 99, 135, 141, 142, 143, 151, 159, 161, 162, 163, 164, 165, 169, 175, 179, 182, 184, 186, 188, 190, 197, 203, 204, 211, 215, 220, 227, 228, 232, 235, 238, 239, 243, 244, 248, 250, 257, 262, 267, 270, 272, 275, 277, 282, 290, 291, 293, 294, 297],
    },
}

def sentence_ids_for_group(group_index, direction):
    return GROUP_SENTENCE_IDS.get(group_index, {}).get(direction, [])
