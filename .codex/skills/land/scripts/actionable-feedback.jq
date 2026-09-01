(([ $final_inline[0][].id ] - [ $preliminary_inline[0][].id ]) | length) +
(([ $final_comments[0][].id ] - [ $preliminary_comments[0][].id ]) | length) +
([ $final_reviews[0]
   | map(select(.state == "APPROVED" or .state == "CHANGES_REQUESTED"))
   | sort_by(.submitted_at // "")
   | group_by(.user.login // "")[]
   | last
   | select(.state == "CHANGES_REQUESTED")
 ] | length)
