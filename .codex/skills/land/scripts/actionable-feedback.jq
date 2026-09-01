def feedback_fingerprint: {
  id,
  body: (.body // ""),
  updated_at: (.updated_at // "")
};

(([ $final_inline[0][] | feedback_fingerprint ] -
  [ $preliminary_inline[0][] | feedback_fingerprint ]) | length) +
(([ $final_comments[0][] | feedback_fingerprint ] -
  [ $preliminary_comments[0][] | feedback_fingerprint ]) | length) +
(([ $final_reviews[0][]
   | select(((.body // "") | gsub("\\s"; "") | length) > 0)
   | feedback_fingerprint ] -
  [ $preliminary_reviews[0][]
   | select(((.body // "") | gsub("\\s"; "") | length) > 0)
   | feedback_fingerprint ]) | length) +
([ $final_reviews[0]
   | map(select(.state == "APPROVED" or .state == "CHANGES_REQUESTED"))
   | sort_by(.submitted_at // "")
   | group_by(.user.login // "")[]
   | last
   | select(.state == "CHANGES_REQUESTED")
 ] | length)
