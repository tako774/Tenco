#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <sys/time.h>
#include <math.h>
#include <apr_hash.h>

// レート情報構造体
typedef struct {
	double rate;
	double rd_sq;
	apr_hash_t *matched_accounts;
	unsigned int last_timestamp;
	unsigned int counts;
} Rate_info;

// ミリ秒単位のUNIX時刻取得関数
double gettimeofday_sec() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec + (double)tv.tv_usec*1e-6;
}

int main(void) {
	/* 変数定義 */
	const double start_time = gettimeofday_sec();
	const char *REVISION = "0.01";
	
	time_t timer;
	time_t now = time(&timer);
	
	FILE *input_fp = NULL;
	FILE *output_fp = NULL;
	char line[256];

	const char *input_file = "../dat/matched_track_records/2";
	const char *output_file = "../dat/ratings/2";
	const char *output_temp_file = "../dat/ratings/2.temp";
	const char *fmt = "%d,%d,%d,%d,%d,%d,%d\n";
	const int TYPE1_SIZE = 256;
	
	const double INIT_RATE = 1500.0;
	const double MIN_RD = 50.0;      /* Ratings Deviation の最小値 */
	const double MAX_RD = 350.0;     /* Ratings Deviation の最大値 */
	const double MIN_RD_SQ = pow(MIN_RD, 2.0); /* Ratings Deviation の最小値の２乗 */
	const double MAX_RD_SQ = pow(MAX_RD, 2.0); /* Ratings Deviation の最大値の２乗 */
	const double RD_SATURATION_TIME = 365.2422 * 24.0 * 60.0 * 60.0;  /* RD が時間経過で最小から最大まで飽和するまでの秒数 */
	const double RD_DEC = (MAX_RD_SQ - MIN_RD_SQ) / RD_SATURATION_TIME;  /* RD の時間経過に伴う逓減係数 */
	const double Q = log(10.0) / 400.0; /* 定数 */
	const double QIP = 3.0 * pow(Q / M_PI, 2.0); /* 定数 */
	const double B = pow(10.0, 1.0/400.0); /* 定数 */
	const double INV_B = pow(10.0, -1.0/400.0);  /* 定数 */
	
	double rate1;
	double rate2;
	double rd1_sq;
	double rd2_sq;
	double elapsed_time1;
	double elapsed_time2;
	double point1;
	double point2;

	double g_rd1;
	double g_rd2;
	double b_d_rate;
	double g_rd1_b_d_rate;
	double expected_point1;
	double expected_point2;
	double d1_inv_sq;
	double d2_inv_sq;

	unsigned int rep_timestamp;
	unsigned int p1_account_id;
	unsigned int p2_account_id;
	unsigned int p1_type1_id;
	unsigned int p2_type1_id;
	unsigned int p1_points;
	unsigned int p2_points;
	
	unsigned int p1_key;
	unsigned int p2_key;
	unsigned int *p_key;
	Rate_info *p1_rate_info = NULL;
	Rate_info *p2_rate_info = NULL;
	
	int *p1_matched_accounts_key = NULL;
	int *p2_matched_accounts_key = NULL;
	
	apr_pool_t* pool = NULL;
	apr_hash_t* account_type1_rate = NULL;
	
	unsigned int *key = NULL;
	Rate_info *rate_info = NULL;
	apr_hash_index_t *hi = NULL;
	apr_ssize_t klen;
	
	unsigned int track_record_counts = 0;
	
	printf("glicko_ratings_from_file_to_file Rev.%s\n", REVISION);
	
	/* APR準備 */
	apr_initialize();
	apr_pool_create(&pool, NULL);
	
	/* アカウント・キャラ別レート情報ハッシュ */
	account_type1_rate = apr_hash_make(pool);
	
	/* ファイルオープン */
	input_fp = fopen(input_file, "rb");
	if (input_fp == NULL) {
		printf("Error!: input file open error!!(%s)\n");
		exit(EXIT_FAILURE);
	}
	
	output_fp = fopen(output_temp_file, "wb");
	if (output_fp == NULL) {
		printf("Error!: output temp file open error!!(%s)\n");
		exit(EXIT_FAILURE);
	}
	
	while (fgets(line, 256, input_fp) != NULL) {
		
		sscanf(
			line,
			fmt,
			&rep_timestamp,
			&p1_account_id,
			&p2_account_id,
			&p1_type1_id,
			&p2_type1_id,
			&p1_points,
			&p2_points			
		);
		
		// レート情報キーを計算
		// アカウントID×キャラ数上限＋キャラIDをキーとする
		p1_key = p1_account_id * TYPE1_SIZE + p1_type1_id;
		p2_key = p2_account_id * TYPE1_SIZE + p2_type1_id;
		
		// レート情報の取得
		p1_rate_info = (Rate_info *)apr_hash_get(account_type1_rate, &p1_key, sizeof(int));
		p2_rate_info = (Rate_info *)apr_hash_get(account_type1_rate, &p2_key, sizeof(int));
		
		// もしまだデータがなければ初期化
		if (p1_rate_info == NULL) {
			p_key = apr_palloc(pool, sizeof(int));
			p1_rate_info = apr_palloc(pool, sizeof(Rate_info));
			
			*p_key = p1_key;
			p1_rate_info->rate = INIT_RATE;
			p1_rate_info->rd_sq = MAX_RD_SQ;
			p1_rate_info->last_timestamp = rep_timestamp;
			p1_rate_info->counts = 0;
			p1_rate_info->matched_accounts = apr_hash_make(pool);
			
			apr_hash_set(account_type1_rate, p_key, sizeof(int), p1_rate_info);
		}
		if (p2_rate_info == NULL) {
			p_key = apr_palloc(pool, sizeof(int));
			p2_rate_info = apr_palloc(pool, sizeof(Rate_info));
			
			*p_key = p2_key;
			p2_rate_info->rate = INIT_RATE;
			p2_rate_info->rd_sq = MAX_RD_SQ;
			p2_rate_info->last_timestamp = rep_timestamp;
			p2_rate_info->counts = 0;
			p2_rate_info->matched_accounts = apr_hash_make(pool);
			
			apr_hash_set(account_type1_rate, p_key, sizeof(int), p2_rate_info);
		}
		
		// 対戦前レート情報取得
		rate1         = p1_rate_info->rate;
		rd1_sq        = p1_rate_info->rd_sq;
		elapsed_time1 = rep_timestamp - p1_rate_info->last_timestamp;
		rate2         = p2_rate_info->rate;
		rd2_sq        = p2_rate_info->rd_sq;
		elapsed_time2 = rep_timestamp - p2_rate_info->last_timestamp;

		// 対戦結果取得
		if (p1_points > p2_points) {
			point1 = 1.0;
		} else if (p1_points < p2_points) {
			point1 = 0.0;
		} else {
			point1 = 0.5;
		}
		point2 = 1.0 - point1;
		
		/* レート計算 */
			
		// RD の２乗の時間経過による上昇
		rd1_sq = rd1_sq + RD_DEC * elapsed_time1;
		if (rd1_sq > MAX_RD_SQ) rd1_sq = MAX_RD_SQ;
		rd2_sq = rd2_sq + RD_DEC * elapsed_time2;
		if (rd2_sq > MAX_RD_SQ) rd2_sq = MAX_RD_SQ;
		
		// 信頼度による影響低下係数
		g_rd1 = pow(1.0 + QIP * rd1_sq, -0.5);
		g_rd2 = pow(1.0 + QIP * rd2_sq, -0.5);
		// g_rd1 = (1.0 + 3.0 * ((Q * rd1 / Math::PI) ** 2.0)) ** (-0.5)
		// g_rd2 = (1.0 + 3.0 * ((Q * rd2 / Math::PI) ** 2.0)) ** (-0.5)
		
		// 勝利期待値
		b_d_rate = pow(B, rate2 - rate1);
		expected_point1 = 1.0 / (1.0 + pow(b_d_rate, g_rd2));
		g_rd1_b_d_rate  = pow(b_d_rate, g_rd1);
		expected_point2 = g_rd1_b_d_rate / (1.0 + g_rd1_b_d_rate);
		// expected_point1 = 1.0 / (1.0 + 10.0 ** (g_rd2 * (rate2 - rate1) * 0.0025))
		// expected_point2 = 1.0 / (1.0 + 10.0 ** (g_rd1 * (rate1 - rate2) * 0.0025))

		// レート変化の分散の逆数
		d1_inv_sq = pow(Q * g_rd2, 2.0) * expected_point1 * (1.0 - expected_point1);
		d2_inv_sq = pow(Q * g_rd1, 2.0) * expected_point2 * (1.0 - expected_point2);

		// 対戦後RD の２乗
		rd1_sq = 1.0 / (1.0 / rd1_sq + d1_inv_sq);
		if (rd1_sq < MIN_RD_SQ) rd1_sq = MIN_RD_SQ;
		rd2_sq = 1.0 / (1.0 / rd2_sq + d2_inv_sq);
		if (rd2_sq < MIN_RD_SQ) rd2_sq = MIN_RD_SQ;
		
		// 対戦後レート
		rate1 += (Q * rd1_sq) * g_rd2 * (point1 - expected_point1);
		rate2 += (Q * rd2_sq) * g_rd1 * (point2 - expected_point2);
		
		// 計算後レート情報保存
		p1_rate_info->rate = rate1;
		p1_rate_info->rd_sq = rd1_sq;
		p1_rate_info->last_timestamp = rep_timestamp;
		p2_rate_info->rate = rate2;
		p2_rate_info->rd_sq = rd2_sq;
		p2_rate_info->last_timestamp = rep_timestamp;
		
		// 対戦アカウント保存
		p1_matched_accounts_key = apr_palloc(pool, sizeof(int));
		*p1_matched_accounts_key = p2_account_id;
		apr_hash_set(p1_rate_info->matched_accounts, p1_matched_accounts_key, sizeof(int), "");
		
		p2_matched_accounts_key = apr_palloc(pool, sizeof(int));
		*p2_matched_accounts_key = p1_account_id;
		apr_hash_set(p2_rate_info->matched_accounts, p2_matched_accounts_key, sizeof(int), "");
		
		// 対戦数カウント
		p1_rate_info->counts++;
		p2_rate_info->counts++;
		
		// 総対戦数カウント
		track_record_counts++;

	}
	
	printf("★ %d 件の対戦結果を取得\n", track_record_counts);
	printf("rating calculation finished...(%f sec.)\n", gettimeofday_sec() - start_time);
	
	// 現在のRDを算出
	for (hi = apr_hash_first(pool, account_type1_rate); hi; hi = apr_hash_next(hi)) {
		apr_hash_this(hi, (const void **)&key, &klen, (void **)&rate_info);
		rate_info->rd_sq += RD_DEC * (now - rate_info->last_timestamp);
		if (rate_info->rd_sq > MAX_RD_SQ) rate_info->rd_sq = MAX_RD_SQ; 
	}
	
	printf("RD calculation finished...(%f sec.)\n", gettimeofday_sec() - start_time);

	// レート平均を INIT_RATE に合わせる
	double sum = 0.0;
	unsigned int num = 0;
	double avg = 0.0;
	double dif_avg = 0.0; // (目標平均レート - 平均レート)
	for (hi = apr_hash_first(pool, account_type1_rate); hi; hi = apr_hash_next(hi)) {
		apr_hash_this(hi, (const void **)&key, &klen, (void **)&rate_info);
		sum += rate_info->rate;
		num += 1;
	}
	avg = sum / num;
	dif_avg = INIT_RATE - avg;
	for (hi = apr_hash_first(pool, account_type1_rate); hi; hi = apr_hash_next(hi)) {
		apr_hash_this(hi, (const void **)&key, &klen, (void **)&rate_info);
		rate_info->rate += dif_avg;
	}
	
	printf("★ レート平均を %f から %f に調整しました\n", avg, INIT_RATE);
	printf("rate avarage adjusted...(%f sec.)\n", gettimeofday_sec() - start_time);
	
	/* 結果出力 */
	for (hi = apr_hash_first(pool, account_type1_rate); hi; hi = apr_hash_next(hi)) {
		apr_hash_this(hi, (const void **)&key, &klen, (void **)&rate_info);
		fprintf(
			output_fp,
			"%d,%d,%f,%f,%d,%d\n",
			*key / TYPE1_SIZE,
			*key % TYPE1_SIZE,
			rate_info->rate,
			pow(rate_info->rd_sq, 0.5),
			apr_hash_count(rate_info->matched_accounts),
			rate_info->counts
		);
	}
	
	printf("rating info file output...(%f sec.)\n", gettimeofday_sec() - start_time);
	
	/* リソース解放 */
	fclose(input_fp);
	fclose(output_fp);
	apr_pool_destroy(pool);
	apr_terminate();
	
	/* 出力一時ファイルを出力先にリネーム */
	if(rename(output_temp_file, output_file) != 0) {
		printf("Error!: ファイルのリネームに失敗しました(%s -> %s)", output_temp_file, output_file);
		exit(EXIT_FAILURE);
	}
	
	printf("Elapsed Time: %f sec.\n", gettimeofday_sec() - start_time);
	
	return 0;
}

