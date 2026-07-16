#ifndef INCLUDE_STARCE_HPP_
#define INCLUDE_STARCE_HPP_

#include "statistic.hpp"
#include <chrono>
#include <iostream>
#include <regex>
#include <mutex>
#include <thread>

namespace starce
{

class StatisticManager
{
// 完整统计信息
private:
    std::map<EqualSet, DSStatistic *> statistics;

// 用于收集统计信息的临时变量
private:
    mutable EqualSet eset;
    std::vector<EqualSet> subset;
    std::vector<DSStatistic *> subsetStatistics;
    std::vector<bool> skip;
    std::map<std::string, DegreeSequence> singleDS;

// 用于基数估计的信息
private:
    typedef std::pair<idx_t, idx_t> Attribute;
    typedef std::set<Attribute> AttrEset;
    std::vector<AttrEset> attrEsets;
    std::map<idx_t, std::string> tableName;
    std::map<std::pair<idx_t, idx_t>, std::string> columnName;
    std::map<idx_t, idx_t> tabelCard;
    std::map<idx_t, std::string> filterString;
    std::map<std::string, int64_t> relNDV;

public:
    double AdjustRate = 0.1;
    double PredicateAdjustRate = 0.1;
private:
    double rateSum = 0.0;
    int64_t rateCount = 0;

// 分离子查询功能
public:
    bool IsRecordingSubquery = false;
    bool IsRecordEstimateTime = false;
    std::map<std::string, double> RecordingSubqueryTimes;
    bool IsRecordingSingleQuery = true;
    bool SubqueryOutputGroupByMain = false;
    int CurrentMainQueryId = 0;
    std::string CurrentMainQuerySql;
    std::set<std::string> Subqueries;
    std::map<std::string, double> RecordingSubqueryCards;
    std::map<int, std::pair<std::string, std::vector<std::pair<std::string, double>>>> SubqueriesByMainQuery;
    std::set<std::string> SingleQueries;

public:
    bool EnableStarCE = false;
    bool UseSubqueryCard = false;
    bool UseSingleTableCard = false;
    std::map<std::string, int64_t> subqueryCard;
    std::map<std::string, int64_t> singleQueryCard;

public:
    bool IsCollectingRelErr = false;
    double CompressPrecision = 2.0;
    // 真实基数，便于实验对照使用
    std::map<std::string, int64_t> realCard;
    int query_id = 0;
    std::vector<std::pair<int, double>> relErr;

private:
    mutable bool prepared = false;
    // 用于线程安全的锁
    mutable std::mutex statistics_mutex;

// 用于大star拆分特性的变量
public:
    bool EnableStarSplit = false;
    int MaxStarSize = 3;
    std::map<int, int> esetSizeCount;

public:
    int PredMethod = 0; // 0: 调整率, 1: 均匀假设, 2: PM1与上界的度序列平均

private:
    StatisticManager() = default;
    ~StatisticManager() {
        for (auto &statistic : statistics) {
            delete statistic.second;
        }
    }
    StatisticManager(const StatisticManager &) = delete;
    StatisticManager &operator=(const StatisticManager &) = delete;
public:
    static StatisticManager &GetInstance()
    {
        static StatisticManager instance;
        return instance;
    }

public:
    std::string serialize()
    {
        json j;
        for (const auto &statistic : statistics) {
            if (statistic.first.Entries.empty()) {
                continue;
            }
            j["Statistics"].push_back({
                {"EqualSet", statistic.first.serialize_to_json()},
                {"DSStatistic", statistic.second->serialize_to_json()}
            });
        }
        j["AdjustRate"] = AdjustRate;
        return j.dump();
    }
    void deserialize(const std::string &jsonStr)
    {
        json j = json::parse(jsonStr);
        for (const auto &statistic : j.at("Statistics")) {
            EqualSet equalSet;
            equalSet.deserialize(statistic.at("EqualSet"));
            statistics[equalSet] = new DSStatistic(statistic.at("DSStatistic").dump());
            statistics[equalSet]->precision = CompressPrecision;
        }
        AdjustRate = j.at("AdjustRate").get<double>();
        PredicateAdjustRate = AdjustRate;
    }

public:
    void ParsePredicate(std::string sql)
    {
        filterString.clear();
        // select count(*) from ... as ..., ..., ... WHERE ... AND ...;
        std::string from_clause;
        std::string where_clause;
        size_t from_pos = sql.find("FROM");
        size_t where_pos = sql.find("WHERE");
        if (where_pos == std::string::npos) {
            // 没有谓词，略过
            return;
        }
        if (from_pos != std::string::npos) {
            from_clause = sql.substr(from_pos + 4, where_pos - from_pos - 4);
        } else {
            throw std::runtime_error("Invalid SQL: no FROM clause found");
        }
        where_clause = sql.substr(where_pos + 6); // 6 is the length of "WHERE "
        if (*--where_clause.end() == ';') {
            where_clause.erase(where_clause.end() - 1); // 去掉末尾的分号
        }
        // 去除连接条件如 [table_name].[column_name] = [table_name].[column_name]

        // 将剩余的where_clause按 " AND "分离为一组string
        std::vector<std::string> predicates;
        std::vector<bool> visited;
        size_t pos = 0;
        std::regex join_regex(R"((\w+)\.(\w+)\s*=\s*(\w+)\.(\w+))");
        while ((pos = where_clause.find(" AND ")) != std::string::npos) {
            std::string str = where_clause.substr(0, pos);
            where_clause.erase(0, pos + 5); // 5 is the length of " AND "
            std::smatch match;
            if (std::regex_search(str, match, join_regex)) {
                continue;
            }
            predicates.push_back(str);
            visited.push_back(false);
        }
        if (!where_clause.empty()) {
            std::smatch match;
            if (!std::regex_search(where_clause, match, join_regex)) {
                predicates.push_back(where_clause);
                visited.push_back(false);
            }
        }

        // 解析from_clause，获取表名和别名
        // 按", "分割
        std::vector<std::string> tables;
        std::vector<std::string> alias;
        // 匹配所有 table_name AS alias_name模式
        std::regex table_regex(R"((\w+)(?:\s[aA][sS]\s+(\w+))?)");
        std::sregex_iterator it(from_clause.begin(), from_clause.end(), table_regex);
        std::sregex_iterator end;
        while (it != end) {
            std::smatch match = *it;
            tables.push_back(match[1].str());
            if (match.size() > 2 && !match[2].str().empty()) {
                alias.push_back(match[2].str());
            } else {
                throw std::runtime_error("Table alias is required in FROM clause: " + match[1].str());
            }
            ++it;
        }

        // 枚举每张表，在predicates中查找是否有该表的谓词
        // 如果有，标记visited，如果已经visited，报错
        for (size_t i = 0; i < tables.size(); ++i) {
            std::string table = tables[i];
            std::string table_alias = alias[i];
            std::string conj_pred;
            bool first = true;
            for (size_t j = 0; j < predicates.size(); ++j) {
                std::string predicate = " " + predicates[j];
                // 匹配 table_alias + "."，要求table_alias全字匹配
                if (predicate.find(" " + table_alias + ".") != std::string::npos) {
                    if (visited[j]) {
                        throw std::runtime_error("Duplicate table for predicate: " + predicate);
                    }
                    visited[j] = true;
                    // 将谓词中的别名替换为字符串"__table_name"
                    std::regex alias_regex(" " + table_alias + R"(\.(\w+))");
                    predicate = std::regex_replace(predicate, alias_regex, " __table_name.$1");
                    if (first) {
                        first = false;
                    } else {
                        conj_pred += " AND ";
                    }
                    conj_pred += predicate.substr(1);
                }
            }
            filterString[i] = conj_pred;
            // std::cerr << table_alias << ' ' << conj_pred << std::endl;
        }
    }

    int64_t GetTableCard(idx_t idx)
    {
        // 为了保持记录的单表子查询稳定，没有filter不记录
        if (filterString.at(idx).empty()) {
            return static_cast<int64_t>(tabelCard.at(idx));
        }
        if (IsRecordingSingleQuery) {
            RecordSingleQuery(idx);
        }
        if (!UseSingleTableCard) {
            return static_cast<int64_t>(tabelCard.at(idx));
        } else {
            if (singleQueryCard.count(GetSingleQuery(static_cast<int64_t>(idx))) == 0) {
                throw std::runtime_error("No single table card for table: " + GetSingleQuery(static_cast<int64_t>(idx)));
            }
            return static_cast<int64_t>(singleQueryCard.at(GetSingleQuery(static_cast<int64_t>(idx))));
        }
    }

    void CalcAdjustRate()
    {
        if (rateCount > 0) {
            AdjustRate = rateSum / static_cast<double>(rateCount);
            PredicateAdjustRate = AdjustRate;
        }
    }

    void PrepareCollection(const EqualSet &eset)
    {
        this->eset = eset;
        if (EnableStarSplit) {
            eset.GetAllSubsetLimitSize(subset, MaxStarSize);
        } else {
            eset.GetAllSubset(subset);
        }
        subsetStatistics.resize(subset.size());
        skip.resize(subset.size());
        int i = 0;
        for (const auto &sub : subset) {
            if (statistics.count(sub) != 0) {
                subsetStatistics[i] = nullptr;
                skip[i] = true;
            } else {
                subsetStatistics[i] = statistics[sub] = new DSStatistic(sub.GetTableList(), CompressPrecision);
                skip[i] = false;
            }
            ++i;
        }
        singleDS.clear();
        for (const auto &entry : eset.Entries) {
            const std::string table_name = entry.TableName;
            singleDS[table_name] = DegreeSequence();
        }
    }

    void AddDegree(const std::map<Table, int64_t> &count, int count_count = 1)
    {
        // int zeroSet = 0;
        // int i = 0;
        // for (const auto &entry : eset.Entries) {
        //     if (count.count(entry.TableName) == 0
        //         || count.at(entry.TableName) == 0) {
        //         zeroSet |= 1 << i;
        //     }
        //     ++i;
        // }
        for (size_t s = 0; s < subset.size(); ++s) {
            if (skip[s]) { continue; }
            subsetStatistics[s]->AddDegree(count, count_count);
        }
        AddDegreeForSingleDS(count, count_count);
    }

    void AddDegreeForSingleDS(const std::map<Table, int64_t> &count, int count_count = 1)
    {
        for (const auto &kv : count) {
            const std::string &table_name = kv.first;
            int64_t cnt = kv.second;
            if (cnt == 0) { continue; }
            if (singleDS.count(table_name) == 0) {
                throw std::runtime_error("Table " + table_name + " not found in singleDS");
            }
            singleDS[table_name].AddDegree(static_cast<double>(cnt), count_count, CompressPrecision);
        }
    }

    void FinishCollection()
    {
        for (size_t s = 0; s < subset.size(); ++s) {
            if (skip[s]) { continue; }
            subsetStatistics[s]->FinishCollection();
        }
        // 计算均化参数
        for (const auto &entry : eset.Entries) {
            const std::string &table_name = entry.TableName;
            if (singleDS.count(table_name) == 0) {
                throw std::runtime_error("Table " + table_name + " not found in singleDS");
            }
            singleDS[table_name].FinishCollection();
        }
        for (size_t s = 0; s < subset.size(); ++s) {
            if (skip[s]) { continue; }
            if (subset[s].Entries.size() <= 1) { continue; }
            bool is_first = true;
            DegreeSequence ds;
            double avg_card = 1;
            for (const auto &entry : subset[s].Entries) {
                const std::string &table_name = entry.TableName;
                if (singleDS.count(table_name) == 0) {
                    throw std::runtime_error("Table " + table_name + " not found in singleDS");
                }
                if (is_first) {
                    ds = singleDS.at(table_name);
                    avg_card = ds.GetCard();
                    is_first = false;
                } else {
                    const DegreeSequence &single = singleDS.at(table_name);
                    avg_card *= single.GetCard() / std::max<int64_t>(ds.GetNDV(), single.GetNDV());
                    ds = ds.dot(singleDS.at(table_name), CompressPrecision);
                }
            }
            double real_card = subsetStatistics[s]->card;
            double upp_card = ds.GetCard();
            if (upp_card <= avg_card) {
                continue;
            }
            double k = std::max<double>(0, (real_card - avg_card) / (upp_card - avg_card));
            double rate = pow(k, 1.0f / static_cast<float>(subset[s].Entries.size()));
            rateSum += rate;
            rateCount++;
            // std::cout << "adjust_rate: " << k << ' ' << subset.at(s).Entries.size() << ' ' << rate << std::endl;
        }
    }

    void PrepareEstimate()
    {
        if (prepared) {
            throw std::runtime_error("Already prepared for estimation");
        }
        attrEsets.clear();
        tableName.clear();
        columnName.clear();
        tabelCard.clear();
        prepared = true;
        query_id++;
    }

    void FinishEstimate() const
    {
        prepared = false;
    }

    void AddTable(idx_t table_id, const std::string &table_name,
                  const std::vector<std::string> &column_names, idx_t card = 0)
    {
        tableName[table_id] = table_name;
        for (idx_t i = 0; i < column_names.size(); ++i) {
            std::string column_name = column_names[i];
            if (column_name.find('.') != std::string::npos) {
                column_name = column_name.substr(column_name.find('.') + 1);
            }
            columnName[{table_id, i}] = column_name;
        }
        tabelCard[table_id] = card;
        relNDV[std::to_string(table_id)] = GetNDV(table_name);
        // filterString[table_id] = filter;
    }

    void AddPredicate(idx_t table1, idx_t table2, idx_t column1, idx_t column2)
    {
        int idx1 = -1;
        int idx2 = -1;
        int i = 0;
        for (auto &eset : attrEsets) {
            if (eset.find({table1, column1}) != eset.end()) {
                idx1 = i;
            } else if (eset.find({table2, column2}) != eset.end()) {
                idx2 = i;
            }
            ++i;
        }
        if (idx1 == -1 && idx2 == -1) {
            attrEsets.push_back({{table1, column1}, {table2, column2}});
        } else if (idx1 == -1) {
            attrEsets[idx2].insert({table1, column1});
        } else if (idx2 == -1) {
            attrEsets[idx1].insert({table2, column2});
        } else {
            attrEsets[idx1].insert(attrEsets[idx2].begin(), attrEsets[idx2].end());
            attrEsets.erase(attrEsets.begin() + idx2);
        }
    }

    std::vector<AttrEset> GetAttrEsetFromRels(const std::vector<idx_t> &rels) const
    {
        std::map<idx_t, bool> vis;
        std::vector<AttrEset> result;
        for (const auto &attrEset : attrEsets) {
            AttrEset eset;
            for (const auto &attr: attrEset) {
                if (std::find(rels.begin(), rels.end(), attr.first) != rels.end()) {
                    eset.insert(attr);
                }
            }
            if (eset.size() > 1) {
                result.push_back(eset);
                for (const auto &attr : eset) {
                    vis[attr.first] = true;
                }
            }
        }
        for (idx_t rel : rels) {
            if (!vis[rel]) {
                AttrEset eset;
                eset.insert({rel, 0});
                result.push_back(eset);
            }
        }
        return result;
    }

    EqualSet GetEqualSetFromAttrEset(const AttrEset &attrEset, std::map<std::string, idx_t> &tableIdx) const
    {
        EqualSet eset;
        if (attrEset.size() == 1) {
            auto it = attrEset.begin();
            eset.Entries.insert({tableName.at(it->first), ""});
            tableIdx[tableName.at(attrEset.begin()->first)] = attrEset.begin()->first;
            return eset;
        }
        for (const auto &attr : attrEset) {
            eset.Entries.insert({tableName.at(attr.first), columnName.at(attr)});
            tableIdx[tableName.at(attr.first)] = attr.first;
        }
        return eset;
    }

    bool CanMerge(const AttrEset &eset1, const AttrEset &eset2) const
    {
        for (const auto &attr1 : eset1) {
            for (const auto &attr2 : eset2) {
                if (attr1.first == attr2.first) {
                    return true;
                }
            }
        }
        return false;
    }

    idx_t GetCommonRelation(const AttrEset &eset1, const AttrEset &eset2) const
    {
        for (const auto &attr1 : eset1) {
            for (const auto &attr2 : eset2) {
                if (attr1.first == attr2.first) {
                    return attr1.first;
                }
            }
        }
        return -1;
    }

    std::string GetSubquery(const std::vector<idx_t>& rels, const std::vector<AttrEset> &attrEsets)
    {
        std::map<idx_t, int> alias_id;
        auto to_alias = [&] (idx_t rel) {
            int id = alias_id[rel];
            std::string alias_name = tableName.at(rel) + std::to_string(id);
            // std::string alias_name = std::string() + tableName.at(rel)[0] + std::to_string(rel);
            return alias_name;
        };
        std::map<std::string, int> cur_alias_id;
        for (idx_t rel : rels) {
            std::string table_name = tableName.at(rel);
            alias_id[rel] = ++cur_alias_id[table_name];
        }
        std::string sql = "SELECT COUNT(*) FROM ";

        // from clause
        std::vector<std::string> from_items;
        for (idx_t rel : rels) {
            std::string table_name = tableName.at(rel);
            from_items.push_back(table_name + " AS " + to_alias(rel));
        }
        sort(from_items.begin(), from_items.end());
        bool is_first = true;
        for (const std::string &from_item : from_items) {
            if (is_first) {
                sql += from_item;
                is_first = false;
            } else {
                sql = sql + "," + from_item;
            }
        }

        // join conditions
        std::vector<std::string> join_conditions;
        for (const AttrEset &eset : attrEsets) {
            std::string last_attr = "";
            if (eset.size() == 1) {
                continue;
            }
            for (const Attribute& attr : eset) {
                std::string attr_str = to_alias(attr.first) + "." + columnName.at(attr);
                if (!last_attr.empty()) {
                    std::string predicate = last_attr + "=" + attr_str;
                    join_conditions.push_back(predicate);
                }
                last_attr = attr_str;
            }
        }
        sort(join_conditions.begin(), join_conditions.end());
        is_first = true;
        for (const std::string &join_cond : join_conditions) {
            if (is_first) {
                sql = sql + " WHERE " + join_cond;
                is_first = false;
            } else {
                sql = sql + " AND " + join_cond;
            }
        }

        // predicates
        std::vector<std::string> predicates;
        for (idx_t rel : rels) {
            if (!filterString.at(rel).empty()) {
                std::string filter = filterString.at(rel);
                size_t pos = 0;
                while ((pos = filter.find("__table_name", pos)) != std::string::npos) {
                    filter.replace(pos, 12, to_alias(rel));
                    pos += to_alias(rel).length();
                }
                // 对filter再进行一些处理：先按" AND "拆分，然后排序，然后将排好序的一一加入predicates
                std::vector<std::string> filter_predicates;
                size_t pred_pos = 0;
                std::string filter_copy = filter;
                while ((pred_pos = filter_copy.find(" AND ")) != std::string::npos) {
                    std::string single_pred = filter_copy.substr(0, pred_pos);
                    filter_predicates.push_back(single_pred);
                    filter_copy.erase(0, pred_pos + 5); // length of " AND "
                }
                if (!filter_copy.empty()) {
                    filter_predicates.push_back(filter_copy);
                }
                std::sort(filter_predicates.begin(), filter_predicates.end());
                for (const auto& pred : filter_predicates) {
                    predicates.push_back(pred);
                }
                continue;
            }
        }
        sort(predicates.begin(), predicates.end());
        for (const std::string &pred : predicates) {
            if (is_first) {
                sql = sql + " WHERE " + pred;
                is_first = false;
            } else {
                sql = sql + " AND " + pred;
            }
        }
        sql += ';';
        return sql;
    }

    std::string GetSingleQuery(idx_t rel)
    {
        std::string result = "SELECT COUNT(*) FROM ";
        std::string table_name = tableName.at(rel);
        result += table_name;
        if (!filterString.at(rel).empty()) {
            std::string filter = filterString.at(rel);
            size_t pos = 0;
            while ((pos = filter.find("__table_name", pos)) != std::string::npos) {
                filter.replace(pos, 12, tableName.at(rel));
                pos += tableName.at(rel).length();
            }
            result += " WHERE " + filter;
        }
        result += ';';
        return result;
    }

    void RecordSubquery(const std::string& subquery, double card)
    {
        Subqueries.insert(subquery);
        RecordingSubqueryCards[subquery] = card;
        if (SubqueryOutputGroupByMain) {
            auto &entry = SubqueriesByMainQuery[CurrentMainQueryId];
            if (entry.first.empty()) {
                entry.first = CurrentMainQuerySql;
            }
            entry.second.emplace_back(subquery, card);
        }
    }

    void AddSubqueryCard(const std::string& subquery, int64_t card) {
        subqueryCard[subquery] = card;
    }

    void AddRealCard(const std::string& table, int64_t card) {
        realCard[table] = card;
    }

    void RecordSingleQuery(idx_t rel)
    {
        SingleQueries.insert(GetSingleQuery(rel));
    }

    void AddSingleQueryCard(const std::string& query, int64_t card) {
        singleQueryCard[query] = card;
    }

    int64_t GetNDV(const std::string& table)
    {
        EqualSet eset;
        eset.Entries.insert({table, ""});
        if (statistics.count(eset) == 0) {
            throw std::runtime_error("No statistics for " + eset.serialize());
        }
        return static_cast<int64_t>(statistics.at(eset)->card);
    }

    DSStatistic GetStatisticsFromEset(const EqualSet &eset)
    {
        if (!EnableStarSplit) {
            esetSizeCount[static_cast<int>(eset.Entries.size())]++;
            if (statistics.count(eset) == 0) {
                throw std::runtime_error("No statistics for " + eset.serialize());
            }
            auto &result = *statistics.at(eset);
            return result;
        }
        bool is_first = true;
        std::vector<EqualSet> subsets;
        DSStatistic result(std::vector<Table>{}, CompressPrecision);
        eset.Split(subsets, MaxStarSize);
        for (auto &subset : subsets) {
            if (statistics.count(subset) == 0) {
                throw std::runtime_error("No statistics for subset " + subset.serialize() + " of " + eset.serialize());
            }
            DSStatistic ds = *statistics.at(subset);
            if (is_first) {
                is_first = false;
                result = ds;
                result.precision = CompressPrecision;
            } else {
                result.MergeByCenter(ds);
            }
        }
        return result;
    }

    double EstimateCardinality(const std::vector<idx_t>& rels)
    {
        double card = 1;
        std::vector<AttrEset> attrEsets = GetAttrEsetFromRels(rels);
#ifdef DEBUG
        static int call_id = 0;
        int my_call_id = ++call_id;
        { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
          fprintf(dbg, "[DEBUG #%d] EstimateCardinality: rels=%zu attrEsets=%zu PredMethod=%d filterString=%zu\n",
                  my_call_id, rels.size(), attrEsets.size(), PredMethod, filterString.size());
          for (auto &r : rels) fprintf(dbg, "  rel=%lu\n", (unsigned long)r);
          fclose(dbg); }
#endif
        std::vector<int> parent(attrEsets.size());
        std::vector<DSStatistic> dsStats;
        std::string subquery;
        if (IsRecordingSubquery || IsRecordEstimateTime) {
            subquery = GetSubquery(rels, attrEsets);
        }
        if (UseSubqueryCard) {
            subquery = GetSubquery(rels, attrEsets);
            if (subqueryCard.count(subquery) == 0) {
                throw std::runtime_error("No subquery card for " + subquery);
            }
            if (IsCollectingRelErr) {
                double rel_err = static_cast<double>(subqueryCard.at(subquery)) / static_cast<double>(realCard.at(subquery));
                relErr.emplace_back(query_id, rel_err);
            }
            return static_cast<double>(subqueryCard.at(subquery));
        }

        auto _est_start = std::chrono::high_resolution_clock::now();

        for (int i = 0; i < attrEsets.size(); ++i) {
            parent[i] = i;
            std::map<std::string, idx_t> tableIdx;
            EqualSet eset = GetEqualSetFromAttrEset(attrEsets[i], tableIdx);
            dsStats.emplace_back(GetStatisticsFromEset(eset), tableIdx);
            // if (PredMethod == 0) {
                // dsStats[i].AdjustToAverage(relNDV, AdjustRate);
            // }
        }

        if (PredMethod == 0) {
#ifdef DEBUG
            { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
              fprintf(dbg, "[DEBUG] PM0 block entered, attrEsets=%zu\n", attrEsets.size());
              fclose(dbg); }
#endif
            for (int i = 0; i < attrEsets.size(); ++i) {
#ifdef DEBUG
                { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
                  fprintf(dbg, "[DEBUG] PM0 i=%d attrEsetSize=%zu filterString entries:\n", i, attrEsets[i].size());
                  for (const auto &attr : attrEsets[i]) {
                    idx_t rel_id = attr.first;
                    bool has_filter = !filterString.at(rel_id).empty();
                    fprintf(dbg, "  rel=%lu hasFilter=%d filter='%s'\n", (unsigned long)rel_id, has_filter, has_filter ? filterString.at(rel_id).c_str() : "(empty)");
                  }
                  fclose(dbg); }
#endif
                for (const auto &attr : attrEsets[i]) {
                    idx_t rel_id = attr.first;
                    if (!filterString.at(rel_id).empty()) {
                        double oldCard = dsStats[i].card;
                        double fc = static_cast<double>(GetTableCard(rel_id)) / GetNDV(tableName.at(rel_id));
                        DSStatistic singleStats(std::to_string(rel_id), static_cast<double>(GetTableCard(rel_id)), CompressPrecision);
                        singleStats.AdjustToAverage(relNDV, PredicateAdjustRate);
                        dsStats[i].Merge(singleStats, std::to_string(rel_id));
#ifdef DEBUG
                        { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
                          fprintf(dbg, "[DEBUG PM0] i=%d table=%lu fc=%.6f card: %.1f -> %.1f\n",
                                  i, (unsigned long)rel_id, fc, oldCard, dsStats[i].card);
                          fclose(dbg); }
#endif
                    }
                }
            }
        } else if (PredMethod == 2) {
            for (int i = 0; i < attrEsets.size(); ++i) {
                for (const auto &attr : attrEsets[i]) {
                    idx_t rel_id = attr.first;
                    if (!filterString.at(rel_id).empty()) {
                        std::string table_name = std::to_string(rel_id);
                        double filtered_card = static_cast<double>(GetTableCard(rel_id));
                        int64_t ndv = GetNDV(tableName.at(rel_id));
                        double filter_coeff = filtered_card / static_cast<double>(ndv);
                        double k = PredicateAdjustRate;
                        // k 权重 UB 侧（PM0 惯例：低=保守/PM1，高=上界）
                        // overlap: PM1_weight * fc + UB_weight * 1
                        double overlap_factor = filter_coeff * (1.0 - k) + 1.0 * k;
                        // tail: PM1_weight * fc + UB_weight * 0
                        double tail_factor = filter_coeff * (1.0 - k);

                        DegreeSequence &orig_ds = dsStats[i].ds[table_name];
                        DegreeSequence filter_ds;
                        // 按 distinct value 计数划分（与 UB 的 all-1 序列长度 filtered_card 一致）
                        // PM2 始终保留 tail（PM1 保留它，UB 置零，加权平均后非零）
                        int64_t fc_vals = static_cast<int64_t>(filtered_card);
                        int64_t pos = 0;
                        for (size_t j = 0; j < orig_ds.count.size(); j++) {
                            int64_t c = orig_ds.count[j];
                            int64_t overlap = 0;
                            if (pos < fc_vals) {
                                overlap = std::min(c, fc_vals - pos);
                                filter_ds.AddDegree(overlap_factor, overlap, CompressPrecision);
                            }
                            int64_t tail = c - overlap;
                            if (tail > 0 && tail_factor > 0.0) {
                                filter_ds.AddDegree(tail_factor, tail, CompressPrecision);
                            }
                            pos += c;
                        }
                        filter_ds.FinishCollection();

                        DSStatistic singleStats(table_name, filtered_card, CompressPrecision);
                        singleStats.ds[table_name] = filter_ds;
                        dsStats[i].Merge(singleStats, table_name);
                    }
                }
            }
        } else {
            for (int i = 0; i < attrEsets.size(); ++i) {
                // 首先计算出所有 filter_coeff
                std::vector<std::pair<double, Attribute>> table_coeffs;
                for (const auto &attr : attrEsets[i]) {
                    idx_t rel_id = attr.first;
                    if (!filterString.at(rel_id).empty()) {
                        double filter_coeff = static_cast<double>(GetTableCard(rel_id)) / GetNDV(tableName.at(rel_id));
                        table_coeffs.emplace_back(filter_coeff, attr);
                    }
                }
                // 对 coeffs 按小到大排序
                std::sort(table_coeffs.begin(), table_coeffs.end(),
                        [] (const std::pair<double, Attribute> &lhs, const std::pair<double, Attribute> &rhs) {
                            return lhs.first < rhs.first;
                        });
                // 对每个 coeff 进行 pow(val, 1 / (idx+1)) 处理
                double coeff = 1;
                AttrEset refine_attr_eset;
                for (size_t j = 0; j < table_coeffs.size(); ++j) {
                    double single_coeff = table_coeffs[j].first;
                    const Attribute &attr = table_coeffs[j].second;
                    idx_t rel_id = attr.first;
                    coeff *= std::pow(single_coeff, 1.0 / static_cast<double>(j + 1));

                    // 维护 refine equalset
                    refine_attr_eset.insert(attr);
                    std::map<std::string, idx_t> table_idx;
                    EqualSet refine_eset = GetEqualSetFromAttrEset(refine_attr_eset, table_idx);
                    auto stat_it = statistics.find(refine_eset);
                    if (stat_it != statistics.end() && stat_it->second->card > 0) {
                        double reciprocal = 1.0 / stat_it->second->card;
                        if (coeff < reciprocal) {
                            coeff = reciprocal;
                        }
                    }
                }
                double oldCard = dsStats[i].card;
                dsStats[i].ApplyFilterCoefficient(coeff);
#ifdef DEBUG
                { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
                  fprintf(dbg, "[DEBUG PM1] i=%d coeff=%.6f card: %.1f -> %.1f\n",
                          i, coeff, oldCard, dsStats[i].card);
                  fclose(dbg); }
#endif
            }
        }

        for (int i = 0; i < attrEsets.size(); ++i) {
            for (int j = i + 1; j < attrEsets.size(); ++j) {
                if (CanMerge(attrEsets[i], attrEsets[j])) {
                    int root1 = i;
                    int root2 = j;
                    while (parent[root1] != root1) {
                        root1 = parent[root1];
                    }
                    while (parent[root2] != root2) {
                        root2 = parent[root2];
                    }
                    if (root1 != root2) {
                        parent[root2] = root1;
                        idx_t commonRel = GetCommonRelation(attrEsets[root1], attrEsets[root2]);
                        attrEsets[root1].insert(attrEsets[root2].begin(), attrEsets[root2].end());
                        dsStats[root1].AdjustToAverage(relNDV, AdjustRate);
                        dsStats[root2].AdjustToAverage(relNDV, AdjustRate);
                        dsStats[root1].NormalizeSubOneDegrees();
                        dsStats[root2].NormalizeSubOneDegrees();
                        dsStats[root1].Merge(dsStats[root2], std::to_string(commonRel));
                        // dsStats[root1].AdjustToAverage(relNDV, AdjustRate);
                    }
                }
            }
        }
        for (int i = 0; i < attrEsets.size(); ++i) {
            if (parent[i] != i) { continue; }
#ifdef DEBUG
            { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
              fprintf(dbg, "[DEBUG] i=%d root card=%.1f\n", i, dsStats[i].card);
              fclose(dbg); }
#endif
            card *= dsStats[i].card;
        }
#ifdef DEBUG
        { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
          fprintf(dbg, "[DEBUG #%d] final card=%.1f\n", my_call_id, card);
          fclose(dbg); }
#endif
        // std::vector<double> selections;
        // for (int i = 0; i < attrEsets.size(); ++i) {
        //     for (const auto &attr : attrEsets[i]) {
        //         idx_t rel_id = attr.first;
        //         double selection = (double) tabelCard.at(rel_id) / GetNDV(tableName.at(rel_id));
        //         selections.push_back(selection);
        //     }
        // }
        // sort(selections.begin(), selections.end());
        // for (size_t i = 0; i < selections.size(); ++i) {
        //     double selection = pow(selections[i], 1.0 / (i + 1));
        //     card = std::max<int64_t>(1, std::round(card * selection));
        // }
        if (IsRecordEstimateTime) {
            auto _est_end = std::chrono::high_resolution_clock::now();
            std::chrono::duration<double, std::milli> _est_elapsed = _est_end - _est_start;
            RecordingSubqueryTimes[subquery] = _est_elapsed.count();
        }
        if (IsRecordingSubquery) {
            RecordSubquery(subquery, card);
        }
        return card;
    }

    // 获取当前准备的 subset 列表（用于并行处理）
    const std::vector<EqualSet>& GetCurrentSubsets() const {
        return subset;
    }

    // 获取当前准备的 subset 对应的统计信息（用于并行处理）
    const std::vector<DSStatistic*>& GetCurrentSubsetStatistics() const {
        return subsetStatistics;
    }

    // 获取当前的 skip 标记（用于并行处理）
    const std::vector<bool>& GetCurrentSkipFlags() const {
        return skip;
    }

    json MemoryReport() const
    {
        static constexpr size_t kMapNodeOverhead = 40;
        json j;
        size_t total = 0;

        // statistics: 主统计数据
        {
            size_t stats_total = sizeof(statistics);
            for (const auto &kv : statistics) {
                stats_total += kMapNodeOverhead;
                stats_total += kv.first.MemoryUsage();
                stats_total += sizeof(DSStatistic*);
                if (kv.second) {
                    stats_total += kv.second->MemoryUsage();
                }
            }
            j["statistics"]["count"] = statistics.size();
            j["statistics"]["memory"] = stats_total;
            total += stats_total;
        }

        // singleDS: 最后处理的 EqualSet 的单表度序列
        {
            size_t sds_total = sizeof(singleDS);
            for (const auto &kv : singleDS) {
                sds_total += kMapNodeOverhead;
                sds_total += kv.first.capacity() + 1;
                sds_total += kv.second.MemoryUsage();
            }
            j["singleDS"]["count"] = singleDS.size();
            j["singleDS"]["memory"] = sds_total;
            total += sds_total;
        }

        // 收集临时变量: subset, subsetStatistics, skip
        {
            size_t tmp_total = sizeof(subset) + sizeof(subsetStatistics) + sizeof(skip);
            tmp_total += subset.capacity() * sizeof(EqualSet);
            for (const auto &eset : subset) {
                tmp_total += eset.MemoryUsage() - sizeof(EqualSet);
            }
            tmp_total += subsetStatistics.capacity() * sizeof(DSStatistic*);
            tmp_total += skip.capacity() * sizeof(bool);
            j["collection_temporaries"]["memory"] = tmp_total;
            total += tmp_total;
        }

        // 估计相关结构: tableName, columnName, tabelCard, filterString, relNDV, attrEsets
        {
            size_t est_total = sizeof(tableName) + sizeof(columnName) + sizeof(tabelCard)
                             + sizeof(filterString) + sizeof(relNDV) + sizeof(attrEsets);
            for (const auto &kv : tableName) {
                est_total += kMapNodeOverhead + sizeof(idx_t);
                est_total += kv.second.capacity() + 1;
            }
            for (const auto &kv : columnName) {
                est_total += kMapNodeOverhead + sizeof(std::pair<idx_t, idx_t>);
                est_total += kv.second.capacity() + 1;
            }
            for (const auto &kv : tabelCard) {
                est_total += kMapNodeOverhead + sizeof(idx_t) * 2;
            }
            for (const auto &kv : filterString) {
                est_total += kMapNodeOverhead + sizeof(idx_t);
                est_total += kv.second.capacity() + 1;
            }
            for (const auto &kv : relNDV) {
                est_total += kMapNodeOverhead;
                est_total += kv.first.capacity() + 1 + sizeof(int64_t);
            }
            for (const auto &aeset : attrEsets) {
                est_total += sizeof(AttrEset);
                est_total += aeset.size() * (kMapNodeOverhead + sizeof(Attribute));
            }
            j["estimation_structures"]["memory"] = est_total;
            total += est_total;
        }

        // 子查询/实验相关结构
        {
            size_t sq_total = sizeof(Subqueries) + sizeof(RecordingSubqueryCards)
                            + sizeof(SubqueriesByMainQuery) + sizeof(SingleQueries)
                            + sizeof(subqueryCard) + sizeof(singleQueryCard)
                            + sizeof(realCard) + sizeof(relErr) + sizeof(esetSizeCount);
            for (const auto &s : Subqueries) {
                sq_total += kMapNodeOverhead + s.capacity() + 1;
            }
            for (const auto &kv : RecordingSubqueryCards) {
                sq_total += kMapNodeOverhead + kv.first.capacity() + 1 + sizeof(double);
            }
            for (const auto &s : SingleQueries) {
                sq_total += kMapNodeOverhead + s.capacity() + 1;
            }
            for (const auto &kv : subqueryCard) {
                sq_total += kMapNodeOverhead + kv.first.capacity() + 1 + sizeof(int64_t);
            }
            for (const auto &kv : singleQueryCard) {
                sq_total += kMapNodeOverhead + kv.first.capacity() + 1 + sizeof(int64_t);
            }
            for (const auto &kv : realCard) {
                sq_total += kMapNodeOverhead + kv.first.capacity() + 1 + sizeof(int64_t);
            }
            sq_total += relErr.capacity() * sizeof(std::pair<int, double>);
            sq_total += esetSizeCount.size() * (kMapNodeOverhead + sizeof(int) * 2);
            for (const auto &kv : SubqueriesByMainQuery) {
                sq_total += kMapNodeOverhead + sizeof(int) + kv.second.first.capacity() + 1;
                sq_total += kv.second.second.capacity() * sizeof(std::pair<std::string, double>);
                for (const auto &p : kv.second.second) {
                    sq_total += p.first.capacity() + 1;
                }
            }
            j["subquery_structures"]["memory"] = sq_total;
            total += sq_total;
        }

        // 标量成员
        {
            size_t scalar_total = sizeof(AdjustRate) + sizeof(PredicateAdjustRate)
                                + sizeof(rateSum) + sizeof(rateCount)
                                + sizeof(IsRecordingSubquery) + sizeof(IsRecordingSingleQuery)
                                + sizeof(SubqueryOutputGroupByMain) + sizeof(CurrentMainQueryId)
                                + sizeof(EnableStarCE) + sizeof(UseSubqueryCard)
                                + sizeof(UseSingleTableCard) + sizeof(IsCollectingRelErr)
                                + sizeof(CompressPrecision) + sizeof(query_id)
                                + sizeof(prepared) + sizeof(statistics_mutex)
                                + sizeof(EnableStarSplit) + sizeof(MaxStarSize) + sizeof(PredMethod);
            scalar_total += CurrentMainQuerySql.capacity() + 1;
            j["scalar_members"]["memory"] = scalar_total;
            total += scalar_total;
        }

        j["total"] = total;

        // data_only: 纯数据大小（对齐 LpBound 统计口径，不含容器/序列化开销）
        {
            size_t data_only = 0;
            for (const auto &kv : statistics) {
                // EqualSet key: 表名+列名字符串的字节数
                for (const auto &entry : kv.first.Entries) {
                    data_only += entry.TableName.size() + entry.ColumnName.size();
                }
                // DSStatistic: card + 所有 degree sequence bucket
                if (kv.second) {
                    data_only += kv.second->DataSize();
                }
            }
            j["data_only"] = data_only;
        }

        return j;
    }
};
    
} // namespace starce

#endif