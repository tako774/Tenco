#!/usr/bin/sh
export LD_LIBRARY_PATH=/usr/local/apr/lib;

GAME_IDS=(`/usr/bin/ruby get_batch_target_game_ids.rb`)

for ((i = 0; i < ${#GAME_IDS[@]}; i++ ));
do
	time ./glicko_ratings_from_file_to_file ${GAME_IDS[$i]} ../dat/matched_track_records ../dat/ratings false 2>&1;
done
