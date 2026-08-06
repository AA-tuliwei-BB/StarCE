import pandas as pd
import pickle
from DataPrepare.join_data_preparation import JoinDataPreparator
from Models.Bayescard_BN import Bayescard_BN, build_meta_info
import time
from multiprocessing import Pool

def train_DMV(csv_path, model_path, algorithm, max_parents, sample_size):
    data = pd.read_csv(csv_path)
    new_cols = []
    #removing unuseful columns
    for col in data.columns:
        if col in ['VIN', 'Zip', 'City', 'Make', 'Unladen Weight', 'Maximum Gross Weight', 'Passengers',
                   'Reg Valid Date', 'Reg Expiration Date', 'Color']:
            data = data.drop(col, axis=1)
        else:
            new_cols.append(col.replace(" ", "_"))
    data.columns = new_cols
    BN = Bayescard_BN('dmv')
    BN.build_from_data(data, algorithm=algorithm, max_parents=max_parents, ignore_cols=['id'], sample_size=sample_size)
    model_path += f"/{algorithm}_{max_parents}.pkl"
    pickle.dump(BN, open(model_path, 'wb'), pickle.HIGHEST_PROTOCOL)
    print(f"model saved at {model_path}")
    return None

def train_Census(csv_path, model_path, algorithm, max_parents, sample_size):
    df = pd.read_csv(csv_path, header=0, sep=",")
    df = df.drop("caseid", axis=1)
    df = df.dropna(axis=0)
    BN = Bayescard_BN('Census')
    BN.build_from_data(df, algorithm=algorithm, max_parents=max_parents, ignore_cols=['id'], sample_size=sample_size)
    model_path += f"/{algorithm}_{max_parents}.pkl"
    pickle.dump(BN, open(model_path, 'wb'), pickle.HIGHEST_PROTOCOL)
    print(f"model saved at {model_path}")
    return None

def train_imdb(schema, hdf_path, model_folder, algorithm, max_parents, sample_size):
    meta_data_path = hdf_path + '/meta_data.pkl'
    prep = JoinDataPreparator(meta_data_path, schema, max_table_data=20000000)
    #print(f"BN will be trained on the full outer join of following relations")
    for relationship_obj in schema.relationships:
        print(relationship_obj.identifier)

    runtime_fit = 0
    number_of_relations = len(schema.relationships)
    for i, relationship_obj in enumerate(schema.relationships):
        #print("training on relationship_obj.identifier")
        df_sample_size = 10000000
        relation = relationship_obj.identifier
        start_time_sample = time.time()
        df, meta_types, null_values, full_join_est = prep.generate_n_samples(
            df_sample_size, relationship_list=[relation], post_sampling_factor=10)
        end_time_sample = time.time()
        runtime_fit += end_time_sample - start_time_sample
        
        meta_info = build_meta_info(df.columns, null_values)
        start_time_build = time.time()
        bn = Bayescard_BN(relation, meta_info, full_join_est)
        model_path = model_folder + f"/{i}_{algorithm}_{max_parents}.pkl"
        bn.build_from_data(df, algorithm=algorithm, max_parents=max_parents, ignore_cols=['id'],
                           sample_size=sample_size)
        end_time_build = time.time()
        
        runtime_fit += end_time_build - start_time_build
        
        start_time_save_model    = time.time()
        pickle.dump(bn, open(model_path, 'wb'), pickle.HIGHEST_PROTOCOL)
        end_time_save_model = time.time()

    return runtime_fit

def _train_single_relationship(args):
    """Helper function for parallel processing"""
    i, relationship_obj, prep, algorithm, max_parents, sample_size, model_folder = args
    
    runtime_fit = 0
    df_sample_size = 10000000
    relation = relationship_obj.identifier
    
    start_time_sample = time.time()
    df, meta_types, null_values, full_join_est = prep.generate_n_samples(
        df_sample_size, relationship_list=[relation], post_sampling_factor=10)
    end_time_sample = time.time()
    runtime_fit += end_time_sample - start_time_sample
    
    meta_info = build_meta_info(df.columns, null_values)
    start_time_build = time.time()
    bn = Bayescard_BN(relation, meta_info, full_join_est)
    model_path = model_folder + f"/{i}_{algorithm}_{max_parents}.pkl"
    bn.build_from_data(df, algorithm=algorithm, max_parents=max_parents, ignore_cols=['id'],
                       sample_size=sample_size)
    end_time_build = time.time()
    
    runtime_fit += end_time_build - start_time_build
    
    start_time_save_model = time.time()
    pickle.dump(bn, open(model_path, 'wb'), pickle.HIGHEST_PROTOCOL)
    end_time_save_model = time.time()
    
    return runtime_fit

def train_imdb_parallel(schema, hdf_path, model_folder, algorithm, max_parents, sample_size, num_processes=24):
    meta_data_path = hdf_path + '/meta_data.pkl'
    prep = JoinDataPreparator(meta_data_path, schema, max_table_data=20000000)
    
    for relationship_obj in schema.relationships:
        print(relationship_obj.identifier)
    
    # Prepare arguments for parallel processing
    args_list = [
        (i, relationship_obj, prep, algorithm, max_parents, sample_size, model_folder)
        for i, relationship_obj in enumerate(schema.relationships)
    ]
    
    # Create a pool of workers and map the work
    with Pool(processes=num_processes) as pool:
        runtime_fits = pool.map(_train_single_relationship, args_list)
    
    # Sum up all runtimes
    total_runtime = sum(runtime_fits)
    
    return total_runtime

