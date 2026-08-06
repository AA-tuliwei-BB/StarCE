import argparse
import logging
import os
import time

from Join_scheme.data_prepare import convert_time_to_int, preprocess_imdb_light_data
from Evaluation.training import train_one_stats, train_one_imdb
from Evaluation.testing import test_on_stats, test_on_imdb, test_on_imdb_light, test_on_jobm, test_on_jobjoin
from Evaluation.updating import eval_update

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', default='stats', help='Which dataset to be used')
    
    # preprocess data
    parser.add_argument('--preprocess_data', help='Converting date into int', action='store_true')
    parser.add_argument('--data_folder',
                        default='/home/ubuntu/End-to-End-CardEst-Benchmark/datasets/stats_simplified/')
    

    # generate models/ensembles
    parser.add_argument('--generate_models', help='Trains BNs on dataset', action='store_true')
    parser.add_argument('--data_path',
                        default='/home/ubuntu/End-to-End-CardEst-Benchmark/datasets/stats_simplified/{}.csv')
    parser.add_argument('--model_path', default='/home/ubuntu/data_CE/CE_scheme_models/')
    parser.add_argument('--n_dim_dist', type=int, default=2, help="The dimension of the distributions")
    parser.add_argument('--n_bins', type=int, default=None, help="The bin size on the id attributes")
    parser.add_argument('--bucket_method', type=str, default="greedy", help="The bin size on the id attributes")
    parser.add_argument('--external_workload_file', type=str, default=None, help="A query workload to decide n_bins")
    parser.add_argument('--save_bucket_bins', help="Whether want to support data update", action='store_true')
    parser.add_argument('--get_bin_means', help="Setting this will use mean of the bin", action='store_true')
    parser.add_argument('--db_conn_kwargs', type=str,
                        default="dbname=imdb user=postgres password=postgres host=127.0.0.1 port=5436",
                        help="Postgres dsn connection string")
    parser.add_argument('--sample_size', type=int,
                        default=1000000,
                        help='Generate a sample of datasets instead of using the full data')
    parser.add_argument('--prepare_sample',
                        action='store_true',
                        help='Create a temp table for sampling purposes')
    parser.add_argument('--sampling_percentage', type=float,
                        default=1.0,
                        help='Sample rate in percentage')
    parser.add_argument('--sampling_type', type=str,
                        default='ss',
                        help="Type of sampling to use")
    parser.add_argument('--materialize_sample',
                        action='store_true',
                        help='create a materialized sample for the testing queries?')
    parser.add_argument('--seed', type=int, default=0, help="random seed")

    # evaluation
    parser.add_argument('--evaluate', help='Evaluates models to compute cardinality bound', action='store_true')
    parser.add_argument('--model_location', nargs='+',
                        default='/home/ubuntu/data_CE/CE_scheme_models/model_stats_greedy_200.pkl')
    parser.add_argument('--query_file_location', type=str,
                        default=None,
                        help='Location to the test queries')
    parser.add_argument('--ground_true_file_location', type=str,
                        default=None,
                        help='Location to the true cardinality of queries')
    parser.add_argument('--derived_query_file', type=str,
                        default=None,
                        help='Location to the queries and its sub-plan queries')
    parser.add_argument('--query_sample_location', type=str,
                        default=None,
                        help='Location to the pre-materialized sample')
    parser.add_argument('--jobm_mapping_file', type=str,
                        default=None,
                        help='Location to the jobm sub-to-main query mapping')
    parser.add_argument('--save_folder',
                        default='/home/ubuntu/data_CE/CE_scheme_models/')
    
    # debugging
    parser.add_argument('--test_specific_queries', help='Test only Q15, Q20, Q21 for debugging', action='store_true')

    # update
    parser.add_argument('--update_evaluate', help='Train and incrementally update the model', action='store_true')
    parser.add_argument('--split_date', help='which date we want to split the data for update', type=str,
                        default="2014-01-01 00:00:00")
    
    # log level
    parser.add_argument('--log_level', type=int, default=logging.DEBUG)

    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        level=args.log_level,
        # [%(threadName)-12.12s]
        format="%(asctime)s [%(levelname)-5.5s]  %(message)s",
        handlers=[
            logging.FileHandler("logs/{}_{}.log".format(args.dataset, time.strftime("%Y%m%d-%H%M%S"))),
            logging.StreamHandler()
        ])
    logger = logging.getLogger(__name__)

    print(args.dataset)
    if args.dataset == 'stats':
        if args.preprocess_data:
            convert_time_to_int(args.data_folder)
        
        elif args.generate_models:
            start_time = time.time()
            train_one_stats(dataset=args.dataset,
                            data_path=args.data_path,
                            model_folder=args.model_path,
                            n_dim_dist=args.n_dim_dist,
                            n_bins=args.n_bins,
                            bucket_method=args.bucket_method,
                            save_bucket_bins=args.save_bucket_bins,
                            get_bin_means=args.get_bin_means,
                            seed=args.seed)
            end_time = time.time()
            print(f"Training completed: total training time is {end_time - start_time}")
            
        elif args.evaluate:
            save_file = os.path.join(args.save_folder, "stats_CEB_sub_queries_" +
                                     args.model_path.split("/")[-1].split(".pkl")[0] + ".txt")
            test_on_stats(args.model_path, args.query_file_location, save_file)

        elif args.update_evaluate:
            print(args.split_date)
            eval_update(args.data_path, args.model_path, args.n_dim_dist, args.n_bins, args.bucket_method,
                        args.split_date, args.seed)

    elif args.dataset == 'imdb-light':
        if args.preprocess_data:
            preprocess_imdb_light_data(args.data_path, args.query_file_location, args.save_folder)
        if args.generate_models:
            start_time = time.time()
            train_one_stats(dataset=args.dataset,
                            data_path=args.data_path,
                            model_folder=args.model_path,
                            n_dim_dist=args.n_dim_dist,
                            n_bins=args.n_bins,
                            bucket_method=args.bucket_method,
                            save_bucket_bins=args.save_bucket_bins,
                            get_bin_means=args.get_bin_means,
                            seed=args.seed)
            end_time = time.time()
            print(f"Training completed: total training time is {end_time - start_time}")
        if args.evaluate:
            save_file = os.path.join(args.save_folder, "factorjoin_joblight.txt") if args.save_folder else None
            # Support testing specific query indices for debugging
            test_indices = [14, 19, 20] if args.test_specific_queries else None
            test_on_imdb_light(args.model_path, args.query_file_location, args.ground_true_file_location, save_file, test_indices)


    elif args.dataset == 'jobm':
        if args.generate_models:
            start_time = time.time()
            train_one_imdb(args.data_path, args.model_path, args.n_dim_dist, args.n_bins, "fixed_start_key",
                           args.sample_size, args.external_workload_file, args.save_bucket_bins, args.seed,
                           args.prepare_sample, args.db_conn_kwargs, args.sampling_percentage, args.sampling_type,
                           args.query_file_location, args.materialize_sample, dataset='jobm')
            end_time = time.time()
            print(f"Training/Materialization completed: total time is {end_time - start_time}")

        elif args.evaluate:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            proj_root = os.path.normpath(os.path.join(script_dir, "../.."))
            query_file = args.query_file_location or os.path.join(proj_root, "Benchmark/workloads/JOBM/subquery/subquery_from_grouped.sql")
            mapping_file = args.jobm_mapping_file or os.path.join(script_dir, "checkpoints/jobm_sub_to_main.pkl")
            sample_loc = args.query_sample_location or os.path.join(script_dir, "checkpoints/binned_cards_{}/")
            save_folder = os.path.join(proj_root, "Benchmark/workloads/JOBM/subquery/result")
            save_file = os.path.join(save_folder, "factorjoin.txt")
            test_on_jobm(args.model_path, query_file, mapping_file, args.sampling_percentage,
                         sample_loc, save_file)

    elif args.dataset == 'imdb':
        if args.generate_models:
            start_time = time.time()
            train_one_imdb(args.data_path, args.model_path, args.n_dim_dist, args.n_bins, args.bucket_method,
                           args.sample_size, args.external_workload_file, args.save_bucket_bins, args.seed,
                           args.prepare_sample, args.db_conn_kwargs, args.sampling_percentage, args.sampling_type,
                           args.query_file_location, args.materialize_sample)
            end_time = time.time()
            print(f"Training completed: total training time is {end_time - start_time}")

        elif args.evaluate:
            save_file = os.path.join(args.save_folder, "imdb_JOB_sub_queries_" +
                                     args.model_path.split("/")[-1].split(".pkl")[0] + ".txt")
            test_on_imdb(args.model_path, args.query_file_location, args.derived_query_file, args.sampling_percentage,
                         args.query_sample_location, save_file)

    elif args.dataset == 'jobjoin':
        # JobJoin: full 21 tables, pure join workload without predicates, main-query-level evaluation.
        # Use the already-fixed get_cardinality_bound_one (tested on JOBM, identity mapping),
        # In predicate-free scenario, load_sample falls back to ground_truth_factors_no_filter, no PG connection.
        if args.evaluate:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            proj_root = os.path.normpath(os.path.join(script_dir, "../.."))
            query_file = args.query_file_location or os.path.join(script_dir, "checkpoints/jobjoin_queries_clean.sql")
            mapping_file = args.jobm_mapping_file or os.path.join(script_dir, "checkpoints/jobjoin_sub_to_main.pkl")
            sample_loc = args.query_sample_location or os.path.join(script_dir, "checkpoints/binned_cards_{}/")
            save_folder = os.path.join(proj_root, "Benchmark/workloads/JobJoin/result")
            save_file = os.path.join(save_folder, "factorjoin.txt")
            test_on_jobjoin(args.model_path, query_file, mapping_file, args.sampling_percentage,
                            sample_loc, save_file)


