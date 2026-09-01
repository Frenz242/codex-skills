def feedback_fingerprint: {
  id,
  body: (.body // ""),
  updated_at: (.updated_at // "")
};
def human_feedback:
  select(((.body // "") | contains("codex-pull-request-review-summary")) | not);

(([ $final_inline[0][] | feedback_fingerprint ] -
  [ $preliminary_inline[0][] | feedback_fingerprint ]) | length) +
(([ $final_comments[0][] | human_feedback | feedback_fingerprint ] -
  [ $preliminary_comments[0][] | human_feedback | feedback_fingerprint ]) | length) +
(([ $final_reviews[0][]
   | select(((.body // "") | gsub("\\s"; "") | length) > 0)
   | feedback_fingerprint ] -
  [ $preliminary_reviews[0][]
   | select(((.body // "") | gsub("\\s"; "") | length) > 0)
   | feedback_fingerprint ]) | length) +
(([ $final_threads[0][] | select(.isResolved == false) | .id ] -
  [ $preliminary_threads[0][] | select(.isResolved == false) | .id ]) | length) +
([ $final_reviews[0]
   | map(select(.state == "APPROVED" or .state == "CHANGES_REQUESTED"))
   | sort_by(.submitted_at // "")
   | group_by(.user.login // "")[]
   | last
   | select(.state == "CHANGES_REQUESTED")
 ] | length)
