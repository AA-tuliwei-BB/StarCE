#include "duckdb.hpp"
#include "duckdb/starce/starce.hpp"
#include <fstream>
#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include <memory>

bool EnableStarCE = false;
bool UseAssignedAdjustRate = false;
bool UseSubqueryCard = false;
bool RecordingSubquery = false;
bool SubqueryOutputGroupByMain = false;

bool UseSingleTableCard = false;
bool RecordingSingleQuery = false;

bool EnableStarSplit = false;
int MaxStarSize = 3;
int PredMethod = 0; // 0: adjustment rate, 1: uniformity assumption

bool RefreshStatistics = false;
bool IsCollectingRelErr = false;
int CollectParallel = 8;
double CompressPrecision = 2.0;

std::string SCHEMA_PATH;
std::string SUBQUERY_PATH;
std::string SUBQUERY_RESULT_PATH;
std::string SINGLE_QUERY_PATH;
std::string SINGLE_QUERY_RESULT_PATH;
std::string DB_PATH;
std::string STATS_PATH;
std::string SQL_PATH;
std::string REAL_CARD_PATH;
std::string REL_ERR_PATH;
std::string STATS_SIZE_PATH;

bool RecordEstimateTime = false;
std::string SUBQUERY_TIME_PATH;

double ADJUST_RATE = 0.5;
double PREDICATE_ADJUST_RATE = 0.2;

bool TryReadStatistics(const char *path) {
    if (RefreshStatistics) {
        return false;
    }
    std::ifstream file(path);
    if (!file.is_open()) {
        return false;
    }
    // Read file contents
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string jsonStr = buffer.str();

    auto &sm = starce::StatisticManager::GetInstance();
    sm.deserialize(jsonStr);

    file.close();
    return true;
}

void CollectStatistics(const char *db_path, const char *path) {
    // Use a separate connection for statistics collection
    duckdb::DBConfig config;
    config.options.maximum_threads = CollectParallel;
    duckdb::DuckDB db(db_path);
    duckdb::Connection con(db);

    std::vector<starce::EqualSet> esets;

    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(path));
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string jsonStr = buffer.str();

    nlohmann::json jsonData = nlohmann::json::parse(jsonStr);
    nlohmann::json jsonEset = jsonData["EqualSets"];

    for (const auto& json: jsonEset) {
        starce::EqualSet eset;
        eset.deserialize(json);
        esets.push_back(eset);
    }

    starce::StatisticManager &sm = starce::StatisticManager::GetInstance();
    
    // Process each EqualSet
    for (const auto &eset : esets) {
        std::map<std::map<std::string, int64_t>, int64_t> count_num;
        std::cout << "eset size: " << eset.Entries.size() << std::endl;
        
        // Optimized approach: use SQL GROUP BY, join, projection, and aggregation to compute count_num directly
        
        // Step 1: Build subquery - GROUP BY aggregation on each table column
        std::string aggregateQueries = "";
        std::vector<std::pair<std::string, std::string>> tableColumnPairs;
        
        for (const auto &entry : eset.Entries) {
            if (!tableColumnPairs.empty()) aggregateQueries += " UNION ALL ";
            aggregateQueries += "SELECT " + entry.ColumnName + " AS val, '" + entry.TableName + 
                               "' AS tbl, COUNT(*) AS cnt FROM " + entry.TableName + 
                               " WHERE " + entry.ColumnName + " IS NOT NULL GROUP BY " + entry.ColumnName;
            tableColumnPairs.push_back({entry.TableName, entry.ColumnName});
        }
        
        // Step 2: Aggregate all values, project counts per table using CASE WHEN
        std::string caseStatements = "";
        for (size_t i = 0; i < tableColumnPairs.size(); ++i) {
            if (i > 0) caseStatements += ", ";
            const auto &tableName = tableColumnPairs[i].first;
            caseStatements += "COALESCE(SUM(CASE WHEN tbl = '" + tableName + 
                             "' THEN cnt ELSE 0 END), 0) AS " + tableName + "_cnt";
        }
        
        // Step 3: Build intermediate query - summarize counts of all tables per value
        std::string pivotQuery = "SELECT val, " + caseStatements + " FROM (" + 
                                aggregateQueries + ") AS agg_data GROUP BY val";
        
        // Step 4: Build final query - GROUP BY all count combinations to compute count_num
        std::string countNumColumns = "";
        for (size_t i = 0; i < tableColumnPairs.size(); ++i) {
            if (i > 0) countNumColumns += ", ";
            countNumColumns += tableColumnPairs[i].first + "_cnt";
        }
        
        std::string countNumQuery = "SELECT " + countNumColumns + ", COUNT(*) AS freq FROM (" + 
                                   pivotQuery + ") AS pivot_data GROUP BY " + countNumColumns;
        
        // std::cerr << "Executing optimized query for count_num calculation..." << std::endl;
        
        // Step 5: Execute query and read count_num directly
        auto countNumResult = con.Query(countNumQuery);
        // std::cerr << "Query done, RowCount: " << countNumResult->RowCount() << std::endl;
        
        // Step 6: Read count_num mapping from results
        std::unique_ptr<duckdb::DataChunk> chunk;
        while ((chunk = countNumResult->Fetch()) != nullptr) {
            int numTables = tableColumnPairs.size();
            
            for (idx_t row = 0; row < chunk->size(); ++row) {
                std::map<std::string, int64_t> countMap;
                int64_t frequency = 0;
                
                // Read each table count from the first numTables columns
                for (int t = 0; t < numTables; ++t) {
                    auto countValue = chunk->GetValue(t, row);
                    countMap[tableColumnPairs[t].first] = countValue.GetValue<int64_t>();
                }
                
                // The last column is frequency
                auto freqValue = chunk->GetValue(numTables, row);
                frequency = freqValue.GetValue<int64_t>();
                
                count_num[countMap] = frequency;
            }
        }
        
        // std::cerr << "count_num size: " << count_num.size() << std::endl;

        // Step 2: Initialize PrepareCollection
        sm.PrepareCollection(eset);
        
        // Step 3: Get all subsets
        const std::vector<starce::EqualSet>& subsets = sm.GetCurrentSubsets();
        const std::vector<starce::DSStatistic*>& subsetStats = sm.GetCurrentSubsetStatistics();
        const std::vector<bool>& skipFlags = sm.GetCurrentSkipFlags();
        
        // Step 4: Process different subsets in parallel
        int hwThreads = static_cast<int>(std::thread::hardware_concurrency());
        if (hwThreads <= 0) {
            hwThreads = 1;
        }
        int numThreads = std::min((int)subsets.size(), std::min(CollectParallel, hwThreads));
        std::vector<std::thread> threads;

        // std::cerr << "numThreads: " << numThreads << std::endl;
        
        for (int t = 0; t < numThreads; ++t) {
            threads.emplace_back([&](int threadId) {
                // Each thread processes its assigned subset
                for (size_t s = threadId; s < subsets.size(); s += numThreads) {
                    if (skipFlags[s]) continue;
                    
                    // Add all counts from count_num to this subset
                    // count_num is read-only, no locking needed
                    for (const auto &pair : count_num) {
                        subsetStats[s]->AddDegree(pair.first, pair.second);
                    }
                }
            }, t);
        }

        for (const auto &pair :  count_num) {
            sm.AddDegreeForSingleDS(pair.first, pair.second);
        }

        // Wait for all threads to complete
        for (auto &thread : threads) {
            thread.join();
        }

        // Step 5: Finish processing this EqualSet
        sm.FinishCollection();
    }
    
    sm.CalcAdjustRate();
    file.close();

    std::ofstream outputFile(STATS_PATH);
    if (!outputFile.is_open()) {
        throw std::runtime_error("Failed to open output file: statistics.json");
    }
    outputFile << sm.serialize();
    outputFile.close();
}

void Test1(duckdb::Connection &con)
{
    starce::StatisticManager &sm = starce::StatisticManager::GetInstance();
    sm.PrepareEstimate();
    sm.AddTable(0, "users", std::vector<std::string>(1, "Id"));
    sm.AddTable(1, "badges", std::vector<std::string>(1, "UserId"));
    sm.AddPredicate(0, 1, 0, 0);
    std::cout << sm.EstimateCardinality({0, 1}) << std::endl;
}

// select count(*) FROM comments as c, posts as p, postLinks as pl WHERE c.UserId = p.OwnerUserId AND p.Id = pl.PostId;
void Test2(duckdb::Connection &con)
{
    starce::StatisticManager &sm = starce::StatisticManager::GetInstance();
    sm.PrepareEstimate();
    sm.AddTable(0, "comments", std::vector<std::string>({"UserId"}));
    sm.AddTable(1, "posts", std::vector<std::string>({"Id", "OwnerUserId"}));
    sm.AddTable(2, "postLinks", std::vector<std::string>({"PostId"}));
    sm.AddPredicate(0, 1, 0, 1);
    sm.AddPredicate(1, 2, 0, 0);
    std::cout << sm.EstimateCardinality({0, 1, 2}) << std::endl;
}

// select count(*) FROM posts as p, tags as t, votes as v WHERE p.Id = t.ExcerptPostId AND p.OwnerUserId = v.UserId;
void Test3(duckdb::Connection &con)
{
    starce::StatisticManager &sm = starce::StatisticManager::GetInstance();
    sm.PrepareEstimate();
    sm.AddTable(0, "posts", std::vector<std::string>({"Id", "OwnerUserId"}));
    sm.AddTable(1, "tags", std::vector<std::string>({"ExcerptPostId"}));
    sm.AddTable(2, "votes", std::vector<std::string>({"UserId"}));
    sm.AddPredicate(0, 1, 0, 0);
    sm.AddPredicate(0, 2, 1, 0);
    std::cout << sm.EstimateCardinality({0}) << std::endl;
    std::cout << sm.EstimateCardinality({1}) << std::endl;
    std::cout << sm.EstimateCardinality({2}) << std::endl;
    std::cout << sm.EstimateCardinality({0, 1}) << std::endl;
    std::cout << sm.EstimateCardinality({0, 2}) << std::endl;
    std::cout << sm.EstimateCardinality({1, 2}) << std::endl;
    std::cout << sm.EstimateCardinality({0, 1, 2}) << std::endl;
    sm.FinishEstimate();
}

// select count(*) FROM posts as p, tags as t, votes as v WHERE p.Id = t.ExcerptPostId AND p.OwnerUserId = v.UserId;
void Test4(duckdb::Connection &con)
{
    auto result = con.Query("explain select COUNT(*) FROM comments as c, badges as b WHERE c.UserId = b.UserId AND c.Score=0 AND b.Date<='2014-09-11 14:33:06'::timestamp;");
    result->Print();
}

void ExecuteSql(duckdb::Connection &con, const char *path)
{
    // Open file
    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(path));
    }
    int sqlid = 0;
    // Read file line by line
    std::string sql;
    while (std::getline(file, sql)) {
        sqlid++;
        // Trim leading and trailing whitespace
        sql.erase(0, sql.find_first_not_of(" \t\n\r"));
        sql.erase(sql.find_last_not_of(" \t\n\r") + 1);
        if (sql.empty()) {
            continue; // Skip empty lines
        }
        auto &sm = starce::StatisticManager::GetInstance();
        sm.ParsePredicate(sql);
        if (RecordingSubquery) {
            sm.CurrentMainQueryId = sqlid;
            sm.CurrentMainQuerySql = sql;
            if (SubqueryOutputGroupByMain) {
                sm.SubqueriesByMainQuery[sqlid].first = sql;
            }
        }

        // Execute SQL statement
        auto start = std::chrono::high_resolution_clock::now();
        try {
            auto result = con.Query(sql);
            std::cout << "sqlid: " << sqlid << std::endl;
            std::cout << "sql: " << sql << std::endl;
            std::cout << result->ToString();
            // std::cerr << result->ToString() << std::endl;
        } catch (const std::exception &e) {
            std::cerr << "Error executing SQL: " << e.what() << std::endl;
        }
        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> elapsed = end - start;
        std::cout << "runtime: " << elapsed.count() << " ms\n" << std::endl;
    }
    file.close();
}

void OutputSubquery(starce::StatisticManager &sm) {
    std::ofstream file(SUBQUERY_PATH);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SUBQUERY_PATH));
    }
    std::ofstream file_card(SUBQUERY_RESULT_PATH);
    if (!file_card.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SUBQUERY_RESULT_PATH));
    }
    if (SubqueryOutputGroupByMain && !sm.SubqueriesByMainQuery.empty()) {
        for (const auto &kv : sm.SubqueriesByMainQuery) {
            int main_id = kv.first;
            const std::string &main_sql = kv.second.first;
            const auto &subs = kv.second.second;
            file << "=== " << main_id << " ===" << std::endl;
            file << main_sql << std::endl;
            for (const auto &p : subs) {
                file << p.first << std::endl;
            }
        }
        for (const std::string &subquery : sm.Subqueries) {
            file_card << (int64_t)(sm.RecordingSubqueryCards[subquery]) << std::endl;
        }
    } else {
        for (const std::string &subquery : sm.Subqueries) {
            file << subquery << std::endl;
            file_card << (int64_t)(sm.RecordingSubqueryCards[subquery]) << std::endl;
        }
    }
    file.close();
    file_card.close();
}

void OutputSubqueryTime(starce::StatisticManager &sm) {
    std::ofstream file(SUBQUERY_TIME_PATH);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SUBQUERY_TIME_PATH));
    }
    for (const std::string &subquery : sm.Subqueries) {
        auto it = sm.RecordingSubqueryTimes.find(subquery);
        file << (it != sm.RecordingSubqueryTimes.end() ? it->second : 0.0) << std::endl;
    }
    file.close();
}

void ReadSubqueryCard(starce::StatisticManager &sm) {
    // Open file
    std::ifstream file_subquery(SUBQUERY_PATH);
    std::ifstream file_result(SUBQUERY_RESULT_PATH);
    if (!file_subquery.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SUBQUERY_PATH));
    }
    if (!file_result.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SUBQUERY_RESULT_PATH));
    }

    // Read file line by line
    int idx = 0;
    std::string subquery;
    double card;
    while (std::getline(file_subquery, subquery)) {
        ++idx;
        file_result >> card;
        sm.AddSubqueryCard(subquery, int64_t(std::round(card)));
    }
}

void OutputSingleQuery(starce::StatisticManager &sm) {
    // Open file
    std::ofstream file(SINGLE_QUERY_PATH);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SINGLE_QUERY_PATH));
    }
    for (const std::string &query : sm.SingleQueries) {
        file << query << std::endl;
    }
    file.close();
}

void ReadSingleQueryCard(starce::StatisticManager &sm) {
    // Open file
    std::ifstream file_subquery(SINGLE_QUERY_PATH);
    std::ifstream file_result(SINGLE_QUERY_RESULT_PATH);
    if (!file_subquery.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SINGLE_QUERY_PATH));
    }
    if (!file_result.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SINGLE_QUERY_RESULT_PATH));
    }

    // Read file line by line
    std::string query;
    double card;
    while (std::getline(file_subquery, query)) {
        file_result >> card;
        sm.AddSingleQueryCard(query, int64_t(std::round(card)));
    }
}

void ReadRealCard(starce::StatisticManager &sm) {
    // Open file
    std::ifstream file_subquery(SUBQUERY_PATH);
    std::ifstream file_result(REAL_CARD_PATH);
    if (!file_subquery.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(SUBQUERY_PATH));
    }
    if (!file_result.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(REAL_CARD_PATH));
    }

    // Read file line by line
    std::string subquery;
    double card;
    while (std::getline(file_subquery, subquery)) {
        file_result >> card;
        sm.AddRealCard(subquery, int64_t(std::round(card)));
    }
    file_subquery.close();
    file_result.close();
}

void OutputRelErr(starce::StatisticManager &sm) {
    // Open file
    std::ofstream file(REL_ERR_PATH);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(REL_ERR_PATH));
    }
    for (const auto &pair : sm.relErr) {
        file << pair.first << " " << pair.second << std::endl;
    }
    file.close();
}

void OutputStatsSize() {
    auto &sm = starce::StatisticManager::GetInstance();
    nlohmann::json report = sm.MemoryReport();
    std::ofstream file(STATS_SIZE_PATH);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + STATS_SIZE_PATH);
    }
    file << report.dump(2);
    file.close();
}

void ReadConfig(const char *path) {
    // Open file
    std::ifstream file(path);
    if (!file.is_open()) {
        throw std::runtime_error("Failed to open file: " + std::string(path));
    }
    // Read file contents
    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string jsonStr = buffer.str();

    // Parse JSON
    nlohmann::json jsonData = nlohmann::json::parse(jsonStr);

    EnableStarCE = jsonData["EnableStarCE"].get<int>();
    UseAssignedAdjustRate = jsonData["UseAssignedAdjustRate"].get<int>();
    UseSubqueryCard = jsonData["UseSubqueryCard"].get<int>();
    RecordingSubquery = jsonData["RecordingSubquery"].get<int>();
    SubqueryOutputGroupByMain = jsonData["SubqueryOutputGroupByMain"].get<int>();
    UseSingleTableCard = jsonData["UseSingleTableCard"].get<int>();
    RecordingSingleQuery = jsonData["RecordingSingleQuery"].get<int>();
    RefreshStatistics = jsonData["RefreshStatistics"].get<int>();
    EnableStarSplit = jsonData["EnableStarSplit"].get<int>();
    MaxStarSize = jsonData.value("MaxStarSize", 3);
    PredMethod = jsonData["PredMethod"].get<int>();
    IsCollectingRelErr = jsonData["IsCollectingRelErr"].get<int>();
    CollectParallel = jsonData["CollectParallel"].get<int>();
    CompressPrecision = jsonData["CompressPrecision"].get<double>();

    SCHEMA_PATH = jsonData["SCHEMA_PATH"].get<std::string>();
    SUBQUERY_PATH = jsonData["SUBQUERY_PATH"].get<std::string>();
    SUBQUERY_RESULT_PATH = jsonData["SUBQUERY_RESULT_PATH"].get<std::string>();
    SINGLE_QUERY_PATH = jsonData["SINGLE_QUERY_PATH"].get<std::string>();
    SINGLE_QUERY_RESULT_PATH = jsonData["SINGLE_QUERY_RESULT_PATH"].get<std::string>();
    DB_PATH = jsonData["DB_PATH"].get<std::string>();
    STATS_PATH = jsonData["STATS_PATH"].get<std::string>();
    SQL_PATH = jsonData["SQL_PATH"].get<std::string>();
    REAL_CARD_PATH = jsonData["REAL_CARD_PATH"].get<std::string>();
    REL_ERR_PATH = jsonData["REL_ERR_PATH"].get<std::string>();
    STATS_SIZE_PATH = jsonData.value("STATS_SIZE_PATH", "statistics_size.json");

    RecordEstimateTime = jsonData.value("RecordEstimateTime", 0);
    SUBQUERY_TIME_PATH = jsonData.value("SUBQUERY_TIME_PATH", "subquery_time.txt");

    ADJUST_RATE = jsonData["ADJUST_RATE"].get<double>();
    PREDICATE_ADJUST_RATE = jsonData["PREDICATE_ADJUST_RATE"].get<double>();
}

int main() {
    // Create configuration object
    duckdb::DBConfig config;
    config.options.maximum_threads = 1; // Set thread count to 1

    // con.Query("PRAGMA explain_output = 'all';");
    // auto start = std::chrono::high_resolution_clock::now();

    ReadConfig("config.json");

    duckdb::DuckDB db(DB_PATH, &config);
    duckdb::Connection con(db);

    auto &sm = starce::StatisticManager::GetInstance();
    sm.IsRecordingSubquery = RecordingSubquery;
    sm.IsRecordingSingleQuery = RecordingSingleQuery;
    sm.SubqueryOutputGroupByMain = SubqueryOutputGroupByMain;
    sm.UseSubqueryCard = UseSubqueryCard;
    sm.UseSingleTableCard = UseSingleTableCard;
    sm.EnableStarSplit = EnableStarSplit;
    sm.MaxStarSize = MaxStarSize;
    sm.PredMethod = PredMethod;
    sm.IsCollectingRelErr = IsCollectingRelErr;
    sm.CompressPrecision = CompressPrecision;
    sm.IsRecordEstimateTime = RecordEstimateTime;

    if (!TryReadStatistics(STATS_PATH.c_str())) {
        // Collect Statistics
        CollectStatistics(DB_PATH.c_str(), SCHEMA_PATH.c_str());
        if (RefreshStatistics) {
            OutputStatsSize();
        }
    }

    sm.EnableStarCE = EnableStarCE;

    if (UseAssignedAdjustRate) {
        sm.AdjustRate = ADJUST_RATE;
        sm.PredicateAdjustRate = PREDICATE_ADJUST_RATE;
    }

    if (UseSubqueryCard) {
        ReadSubqueryCard(sm);
    }
    if (UseSingleTableCard) {
        ReadSingleQueryCard(sm);
    }
    if (IsCollectingRelErr) {
        ReadRealCard(sm);
    }

    // auto end = std::chrono::high_resolution_clock::now();
    // std::chrono::duration<double, std::milli> elapsed = end - start;
    // std::cout << "Read time: " << elapsed.count() << " ms" << std::endl;

    // Test4(con);
    ExecuteSql(con, SQL_PATH.c_str());

    if (RecordingSubquery) {
        OutputSubquery(sm);
    }
    if (RecordEstimateTime) {
        OutputSubqueryTime(sm);
    }
    if (RecordingSingleQuery) {
        OutputSingleQuery(sm);
    }
    if (IsCollectingRelErr) {
        OutputRelErr(sm);
    }

    if (sm.EnableStarSplit) {
        for (auto &it : sm.esetSizeCount) {
            std::cout << "eset size: " << it.first << ", count: " << it.second << std::endl;
        }
    }

    return 0;
}