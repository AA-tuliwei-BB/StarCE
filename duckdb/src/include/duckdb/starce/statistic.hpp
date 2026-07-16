#ifndef INCLUDE_STARCE_STATISTIC_HPP_
#define INCLUDE_STARCE_STATISTIC_HPP_

#include "equalset.hpp"
#include <iostream>
#include <cmath>

namespace starce
{

typedef uint64_t idx_t;

class DegreeSequence
{
public:
    std::vector<double> maxDegree;
    std::vector<int64_t> count;
    // sum is only used during collection; cleared after FinishCollection; not serialized
    std::vector<double> sum;
    DegreeSequence() = default;

public:
    std::string serialize() const
    {
        return serialize_to_json().dump();
    }

    json serialize_to_json() const
    {
        json j;
        for (size_t i = 0; i < maxDegree.size(); i++) {
            j.push_back({
                {"MaxDegree", maxDegree[i]},
                {"Count", count[i]}
            });
        }
        return j;
    }

    void deserialize(const json &j)
    {
        maxDegree.clear();
        count.clear();
        sum.clear(); // Collection-phase structure; unusable after deserialization
        for (const auto &degree : j) {
            maxDegree.push_back(degree.at("MaxDegree").get<double>());
            count.push_back(degree.at("Count").get<int64_t>());
        }
    }

public:
    void AddDegree(double degree, int64_t count = 1, double precision = 2.0)
    {
        size_t pos = 0;
        if (degree > 1) {
            if (precision <= 1.0) {
                pos = 0;
            } else {
                double log_degree = std::log(degree);
                double log_precision = std::log(precision);
                pos = static_cast<size_t>(std::ceil(log_degree / log_precision));
            }
        }
        if (pos >= maxDegree.size()) {
            maxDegree.resize(pos + 1);
            this->count.resize(pos + 1, 0);
            this->sum.resize(pos + 1, 0.0);
        }
        maxDegree[pos] = std::max(maxDegree[pos], degree);
        this->count[pos] += count;
        this->sum[pos] += degree * static_cast<double>(count);
    }

    void FinishCollection()
    {
        std::reverse(maxDegree.begin(), maxDegree.end());
        std::reverse(count.begin(), count.end());
        std::reverse(sum.begin(), sum.end());
        // Remove elements with zero count
        for (size_t i = 0; i < count.size(); i++) {
            if (count[i] == 0 || maxDegree[i] == 0) {
                maxDegree.erase(maxDegree.begin() + i);
                count.erase(count.begin() + i);
                sum.erase(sum.begin() + i);
                i--;
            }
        }
        // sum correction: tighten count to ceil(sum / maxDegree), fixing count inflation from sub-1 collapsing
        for (size_t i = 0; i < count.size(); i++) {
            double adjusted = std::ceil(sum[i] / maxDegree[i]);
            if (adjusted < static_cast<double>(count[i])) {
                count[i] = static_cast<int64_t>(adjusted);
            }
        }
        sum.clear();
    }

    DegreeSequence dot(const DegreeSequence &other, double precision = 2.0) const {
        DegreeSequence result;
        size_t pos1 = 0, pos2 = 0;
        int64_t count1 = 0, count2 = 0;
        double degree1 = 0, degree2 = 0;
        while (true) {
            if (count1 == 0) {
                if (pos1 >= count.size()) {
                    break;
                }
                count1 = this->count[pos1];
                degree1 = maxDegree[pos1];
                pos1++;
            }
            if (count2 == 0) {
                if (pos2 >= other.count.size()) {
                    break;
                }
                count2 = other.count[pos2];
                degree2 = other.maxDegree[pos2];
                pos2++;
            }
            int64_t count = std::min(count1, count2);
            count1 -= count;
            count2 -= count;
            result.AddDegree(degree1 * degree2, count, precision);
        }
        result.FinishCollection();
        return result;
    }

    DegreeSequence AverageWithTruncation(double filter_coeff, int64_t filtered_card, double k, double precision = 2.0) const {
        DegreeSequence result;
        int64_t pos = 0;
        for (size_t i = 0; i < count.size(); i++) {
            double d = maxDegree[i];
            int64_t c = count[i];
            int64_t overlap = 0;
            if (pos < filtered_card) {
                overlap = std::min(c, filtered_card - pos);
                double overlap_degree = d * (filter_coeff * k + (1.0 - k));
                result.AddDegree(overlap_degree, overlap, precision);
            }
            int64_t tail = c - overlap;
            if (tail > 0) {
                double tail_degree = d * filter_coeff * k;
                result.AddDegree(tail_degree, tail, precision);
            }
            pos += c;
        }
        result.FinishCollection();
        return result;
    }

    double GetCard() const {
        double card = 0;
        for (size_t i = 0; i < count.size(); i++) {
            card += count[i] * maxDegree[i];
        }
        return card;
    }

    int64_t GetNDV() const {
        int64_t ndv = 0;
        for (size_t i = 0; i < count.size(); i++) {
            ndv += count[i];
        }
        return ndv;
    }

    size_t MemoryUsage() const
    {
        size_t total = sizeof(DegreeSequence);
        total += maxDegree.capacity() * sizeof(double);
        total += count.capacity() * sizeof(int64_t);
        total += sum.capacity() * sizeof(double);
        return total;
    }

    size_t DataSize() const
    {
        return count.size() * (sizeof(double) + sizeof(int64_t));
    }
};

class DSStatistic
{
public:
    double card;
    double precision = 2.0;
    DegreeSequence centralDs;
    std::map<Table, DegreeSequence> ds;
    std::vector<Table> tables;
    DSStatistic() = delete;
    explicit DSStatistic(const std::string& str) { deserialize(str); }
    explicit DSStatistic(const std::vector<Table> &tables) : tables(tables), card(0)
    {
        for (const auto &table : tables) {
            ds[table] = DegreeSequence();
        }
    }
    explicit DSStatistic(const std::vector<Table> &tables, double precision) : card(0), precision(precision), tables(tables)
    {
        for (const auto &table : tables) {
            ds[table] = DegreeSequence();
        }
    }
    DSStatistic(const DSStatistic &other, const std::map<std::string, idx_t> &tableIdx)
    {
        card = other.card;
        precision = other.precision;
        for (const auto &table : other.tables) {
            ds[std::to_string(tableIdx.at(table))] = other.ds.at(table);
            tables.push_back(std::to_string(tableIdx.at(table)));
        }
    }
    DSStatistic(const Table &table, double card, double precision_val = 2.0) : card(card), precision(precision_val)
    {
        this->tables.push_back(table);
        DegreeSequence single_ds;
        single_ds.AddDegree(1, static_cast<int64_t>(card), this->precision);
        this->ds[table] = single_ds;
    }

public:
    std::string serialize() const
    {
        return serialize_to_json().dump();
    }

    json serialize_to_json() const
    {
        json j;
        j["Cardinality"] = card;
        j["CentralDS"] = centralDs.serialize_to_json();
        for (const auto &table : tables) {
            j["DSStatistic"].push_back({
                {"Table", table},
                {"DegreeSequence", ds.at(table).serialize_to_json()}
            });
        }
        return j;
    }

    void deserialize(const std::string &jsonStr)
    {
        json j = json::parse(jsonStr);
        card = static_cast<double>(j.at("Cardinality").get<double>());
        centralDs.deserialize(j.at("CentralDS"));
        for (const auto &statistic : j.at("DSStatistic")) {
            Table table = statistic.at("Table").get<std::string>();
            tables.push_back(table);
            ds[table].deserialize(statistic.at("DegreeSequence"));
        }
    }

public:
    void AddDegree(const std::map<Table, int64_t> &count, int64_t count_count = 1)
    {
        int64_t product = 1;
        for (const auto &table : tables) {
            if (count.count(table) == 0 || count.at(table) == 0) {
                return;
            }
            product *= count.at(table);
        }
        if (product == 0) {
            return;
        }
        for (const auto &table : tables) {
            ds[table].AddDegree(product / static_cast<double>(count.at(table)),
                                static_cast<int64_t>(count.at(table)) * count_count,
                                this->precision);
        }
        centralDs.AddDegree(static_cast<double>(product), count_count, this->precision);
        card += static_cast<double>(product) * count_count;
    }

    void FinishCollection()
    {
        for (const auto &table : tables) {
            ds[table].FinishCollection();
        }
        centralDs.FinishCollection();
        LimitAllDsToCard();
        LimitDsToCard(centralDs, card);
    }

    void LimitAllDsToCard()
    {
        for (const Table &table : tables) {
            DegreeSequence &ds = this->ds[table];
            LimitDsToCard(ds, card);
        }
    }

    void LimitDsToCard(DegreeSequence &ds, double card)
    {
        double sum = 0;
        for (size_t i = 0; i < ds.count.size(); i++) {
            if (sum + ds.count[i] * ds.maxDegree[i] <= card) {
                sum += ds.count[i] * ds.maxDegree[i];
            } else if (card - sum <= 1e-6) {
                ds.count.resize(i);
                ds.maxDegree.resize(i);
                break;
            } else if (card - sum < ds.maxDegree[i]) {
                ds.count.resize(i + 1);
                ds.maxDegree.resize(i + 1);
                ds.count[i] = 1;
                ds.maxDegree[i] = card - sum;
                break;
            } else {
                ds.count[i] = floor((card - sum) / ds.maxDegree[i]);
                double newDegree = card - sum - ds.count[i] * ds.maxDegree[i];
                if (newDegree <= 1e-6) {
                    ds.count.resize(i + 1);
                    ds.maxDegree.resize(i + 1);
                } else {
                    ds.count.resize(i + 2);
                    ds.maxDegree.resize(i + 2);
                    ds.count[i + 1] = 1;
                    ds.maxDegree[i + 1] = newDegree;
                }
                break;
            }
        }
    }

    static void AddCurDegree(DSStatistic &newStat,
                      const DSStatistic &oldStat,
                      const Table &mergeTable,
                      std::vector<double>& curDegrees)
    {
        int i = 0;
        for (const Table &table : oldStat.tables) {
            if (table == mergeTable) {
                continue;
            }
            DegreeSequence &newDs = newStat.ds[table];
            double &curDegree = curDegrees[i];
            newDs.AddDegree(curDegree, 1, newStat.precision);
            ++i;
        }
    }

    static void MergeEdgeDegreeSequences(DSStatistic &newStat,
                                         const DSStatistic &oldStat,
                                         const Table &mergeTable,
                                         std::vector<int>& positions,
                                         std::vector<double>& curDegrees,
                                         std::vector<double>& remainRows,
                                         std::vector<int64_t>& remainCounts,
                                         double selfRowNum,
                                         double degree)
    {
        int i = 0;
        for (const Table &table : oldStat.tables) {
            if (table == mergeTable) {
                continue;
            }
            DegreeSequence &newDs = newStat.ds[table];
            const DegreeSequence &oldDs = oldStat.ds.at(table);
            int &pos = positions[i];
            double rownum = selfRowNum;
            double &curDegree = curDegrees[i];
            double &remainRow = remainRows[i];
            int64_t &remainCount = remainCounts[i];
            for (; pos < oldDs.count.size(); pos++) {
                if (remainRow > 0) {
                    if (rownum > remainRow) {
                        rownum -= remainRow;
                        curDegree += remainRow * degree;
                        remainRow = 0;
                        newDs.AddDegree(curDegree, 1, newStat.precision);
                        curDegree = 0;
                        if (remainCount == 0) {
                            continue;
                        }
                    } else {
                        remainRow -= rownum;
                        curDegree += rownum * degree;
                        if (remainRow == 0) {
                            newDs.AddDegree(curDegree, 1, newStat.precision);
                            curDegree = 0;
                            if (remainCount == 0) {
                                pos++;
                            }
                        }
                        break;
                    }
                }
                if (remainCount > 0) {
                    if (rownum > remainCount * oldDs.maxDegree[pos]) {
                        rownum -= remainCount * oldDs.maxDegree[pos];
                        newDs.AddDegree(oldDs.maxDegree[pos] * degree, remainCount, newStat.precision);
                        remainCount = 0;
                        continue;
                    } else {
                        int64_t usedCount = floor(rownum / oldDs.maxDegree[pos]);
                        double usedRow = rownum - usedCount * oldDs.maxDegree[pos];
                        remainCount -= usedCount;
                        if (usedCount > 0) {
                            newDs.AddDegree(oldDs.maxDegree[pos] * degree, usedCount, newStat.precision);
                        }
                        if (usedRow > 1e-6) {
                            remainCount--;
                            remainRow = oldDs.maxDegree[pos] - usedRow;
                            curDegree += usedRow * degree;
                        }
                        if (remainCount == 0 && remainRow == 0) {
                            pos++;
                        }
                        break;
                    }
                }
                if (rownum >= oldDs.count[pos] * oldDs.maxDegree[pos]) {
                    rownum -= oldDs.count[pos] * oldDs.maxDegree[pos];
                    newDs.AddDegree(oldDs.maxDegree[pos] * degree, oldDs.count[pos], newStat.precision);
                } else {
                    int64_t usedCount = floor(rownum / oldDs.maxDegree[pos]);
                    double usedRow = rownum - usedCount * oldDs.maxDegree[pos];
                    remainCount = oldDs.count[pos] - usedCount;
                    if (usedCount > 0) {
                        newDs.AddDegree(oldDs.maxDegree[pos] * degree, usedCount, newStat.precision);
                    }
                    if (usedRow > 1e-6) {
                        remainCount--;
                        remainRow = oldDs.maxDegree[pos] - usedRow;
                        curDegree += usedRow * degree;
                    }
                    break;
                }
            }
            ++i;
        }
    }

    void Merge(const DSStatistic &other, const std::string &table)
    {
        std::vector<Table> newTables = tables;
        for (const auto &t : other.tables) {
            if (std::find(newTables.begin(), newTables.end(), t) == newTables.end()) {
                newTables.push_back(t);
            }
        }
        DSStatistic newStat(newTables, this->precision);
        DegreeSequence &mergeTableDs = newStat.ds[table];
        DegreeSequence ds1 = ds.at(table);
        DegreeSequence ds2 = other.ds.at(table);
        double newCard = 0;
        std::vector<int> position1(tables.size() - 1), position2(other.tables.size() - 1);
        std::vector<double> curDegree1(tables.size() - 1), curDegree2(other.tables.size() - 1);
        std::vector<double> remainRow1(tables.size() - 1), remainRow2(other.tables.size() - 1);
        std::vector<int64_t> remainCount1(tables.size() - 1), remainCount2(other.tables.size() - 1);
        int64_t pointer1 = 0, pointer2 = 0;
        int64_t count1 = 0, count2 = 0;
        double degree1 = 0, degree2 = 0;
        while (true) {
            if (count1 == 0) {
                if (pointer1 >= ds1.count.size()) {
                    break;
                }
                count1 = ds1.count[pointer1];
                degree1 = ds1.maxDegree[pointer1];
                pointer1++;
            }
            if (count2 == 0) {
                if (pointer2 >= ds2.count.size()) {
                    break;
                }
                count2 = ds2.count[pointer2];
                degree2 = ds2.maxDegree[pointer2];
                pointer2++;
            }
            int64_t count = std::min(count1, count2);
            count1 -= count;
            count2 -= count;
            newCard += count * degree1 * degree2;
            mergeTableDs.AddDegree(degree1 * degree2, count, newStat.precision);
            MergeEdgeDegreeSequences(newStat, *this, table, position1, curDegree1, remainRow1, remainCount1,
                                     degree1 * count, degree2);
            MergeEdgeDegreeSequences(newStat, other, table, position2, curDegree2, remainRow2, remainCount2,
                                     degree2 * count, degree1);
        }
        AddCurDegree(newStat, *this, table, curDegree1);
        AddCurDegree(newStat, other, table, curDegree2);
        newStat.card = newCard;
        newStat.FinishCollection();
        newStat.LimitAllDsToCard();
#ifdef DEBUG
        { FILE *dbg = fopen("/tmp/starce_debug.log", "a");
          fprintf(dbg, "[DEBUG Merge] table=%s ds1.card=%.1f ds2.card=%.1f newCard=%.1f\n",
                  table.c_str(), ds1.GetCard(), ds2.GetCard(), newCard);
          fclose(dbg); }
#endif
        *this = newStat;
    }

    void MergeByCenter(const DSStatistic &other)
    {
        // Temporarily add __star_center table to ds, using centralDs as its degree sequence, then call Merge
        std::string centerTable = "__star_center";
        this->tables.push_back(centerTable);
        this->ds[centerTable] = this->centralDs;
        DSStatistic &other_tmp = const_cast<DSStatistic&>(other);
        other_tmp.tables.push_back(centerTable);
        other_tmp.ds[centerTable] = other_tmp.centralDs;

        this->Merge(other, centerTable);
        // TODO-STARCE Maybe: Adjust to Average

        for (auto it = tables.begin(); it != tables.end(); ++it) {
            if (*it == centerTable) {
                tables.erase(it);
                break;
            }
        }
        this->ds.erase(centerTable);
        other_tmp.tables.pop_back();
        other_tmp.ds.erase(centerTable);
    }

    void AdjustToAverage(std::map<std::string, int64_t> ndv, double k)
    {
        for (const auto &table : tables) {
            DegreeSequence &ds = this->ds[table];
            double avgDegree = card / ndv.at(table);
            int64_t zero_count = ndv.at(table);
            for (size_t i = 0; i < ds.maxDegree.size(); ++i) {
                ds.maxDegree[i] = ds.maxDegree[i] * k + avgDegree * (1 - k);
                zero_count -= ds.count[i];
            }
            if (zero_count > 0 && avgDegree * (1 - k) > 0.0) {
                double degree = avgDegree * (1 - k);
                ds.maxDegree.push_back(degree);
                ds.count.push_back(zero_count);
            }
        }
        LimitAllDsToCard();
    }

    void NormalizeSubOneDegrees() {
        for (const auto &table : tables) {
            DegreeSequence &ds = this->ds[table];
            for (size_t i = 0; i < ds.maxDegree.size(); i++) {
                if (ds.maxDegree[i] < 1.0) {
                    ds.count[i] = static_cast<int64_t>(std::ceil(ds.count[i] * ds.maxDegree[i]));
                    if (ds.count[i] < 1) ds.count[i] = 1;
                    ds.maxDegree[i] = 1.0;
                }
            }
        }
        for (size_t i = 0; i < centralDs.maxDegree.size(); i++) {
            if (centralDs.maxDegree[i] < 1.0) {
                centralDs.count[i] = static_cast<int64_t>(std::ceil(centralDs.count[i] * centralDs.maxDegree[i]));
                if (centralDs.count[i] < 1) centralDs.count[i] = 1;
                centralDs.maxDegree[i] = 1.0;
            }
        }
    }

    void ApplyFilterCoefficient(double filter_coeff) {
        // Iterate over degree sequences of all tables
        for (const auto &table : tables) {
            DegreeSequence &ds_ref = this->ds[table];
            // Multiply all degree sequence values by the filter coefficient
            for (size_t i = 0; i < ds_ref.maxDegree.size(); ++i) {
                ds_ref.maxDegree[i] *= filter_coeff;
                if (ds_ref.maxDegree[i] < 1) {
                    ds_ref.count[i] *= ds_ref.maxDegree[i];
                    if (ds_ref.count[i] < 1) {
                        ds_ref.count[i] = 1;
                    }
                    ds_ref.maxDegree[i] = 1;
                }
            }
        }
        // Multiply overall cardinality by the filter coefficient
        card *= filter_coeff;
        if (card < 1) {
            card = 1;
        }
        // Process centralDs
        for (size_t i = 0; i < centralDs.maxDegree.size(); ++i) {
            centralDs.maxDegree[i] *= filter_coeff;
            if (centralDs.maxDegree[i] < 1) {
                centralDs.count[i] *= centralDs.maxDegree[i];
                if (centralDs.count[i] < 1) {
                    centralDs.count[i] = 1;
                }
                centralDs.maxDegree[i] = 1;
            }
        }
    }

    size_t MemoryUsage() const
    {
        static constexpr size_t kMapNodeOverhead = 40;
        size_t total = sizeof(DSStatistic);
        total += centralDs.MemoryUsage() - sizeof(DegreeSequence);
        total += tables.capacity() * sizeof(Table);
        for (const auto &table : tables) {
            total += table.capacity() + 1;
        }
        for (const auto &kv : ds) {
            total += kMapNodeOverhead;
            total += kv.first.capacity() + 1;
            total += kv.second.MemoryUsage();
        }
        return total;
    }

    size_t DataSize() const
    {
        size_t total = sizeof(double); // card
        total += centralDs.DataSize();
        for (const auto &kv : ds) {
            total += kv.second.DataSize();
        }
        return total;
    }
};

} // namespace starce

#endif