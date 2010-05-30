APR_HOME=/usr/local/apr

gcc -g  -lm -I ${APR_HOME}/include/apr-1 -L${APR_HOME}/lib -lapr-1 glicko_ratings_from_file_to_file.c -o ../glicko_ratings_from_file_to_file
