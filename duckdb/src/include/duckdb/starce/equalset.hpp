#ifndef INCLUDE_STARCE_EQUALSET_HPP_
#define INCLUDE_STARCE_EQUALSET_HPP_

#include "json.hpp"
#include <set>

namespace starce
{

using json = nlohmann::json;

typedef std::string Table;

class TableColumn {
public:
    std::string TableName;  // Table name
    std::string ColumnName; // Column name

    // Default constructor
    TableColumn() = default;

    // Parameterized constructor
    TableColumn(const std::string& tableName, const std::string& columnName)
        : TableName(tableName), ColumnName(columnName) {}

    // Serialization: convert object to JSON string
    std::string serialize() const {
        json j = {
            {"TableName", TableName},
            {"ColumnName", ColumnName}
        };
        return j.dump(); // Convert JSON object to string
    }

    // Deserialization: convert JSON string to object
    void deserialize(const std::string& jsonStr) {
        json j = json::parse(jsonStr); // Parse string into JSON object
        TableName = j.at("TableName").get<std::string>();
        ColumnName = j.at("ColumnName").get<std::string>();
    }

    // Overloaded comparison operator
    bool operator<(const TableColumn& other) const {
        if (TableName != other.TableName) {
            return TableName < other.TableName;
        }
        return ColumnName < other.ColumnName;
    }
}; // TableColumn

class EqualSet
{
public:
    std::set<TableColumn> Entries;
    EqualSet() = default;
public:
    // Serialization: convert object to JSON string
    std::string serialize() const {
        return serialize_to_json().dump(); // Convert JSON object to string
    }

    json serialize_to_json() const {
        json j;
        for (const auto& entry : Entries) {
            j["Entries"].push_back({
                {"TableName", entry.TableName},
                {"ColumnName", entry.ColumnName}
            });
        }
        return j;
    }

    // Deserialization: convert JSON string to object
    void deserialize(const std::string& jsonStr) {
        json j = json::parse(jsonStr); // Parse string into JSON object
        deserialize(j);
    }

    // Deserialization: convert JSON string to object
    void deserialize(const json& j) {
        Entries.clear();
        for (const auto& entry : j["Entries"]) {
            TableColumn column(
                entry.at("TableName").get<std::string>(),
                entry.at("ColumnName").get<std::string>()
            );
            Entries.insert(column);
        }
    }

    // Overloaded comparison operator
    bool operator<(const EqualSet& other) const {
        return Entries < other.Entries;
    }

public:
    void GetAllSubset(std::vector<EqualSet>& subset) const {
        subset.clear();
        for (int s = 0; s < 1 << Entries.size(); ++s) {
            EqualSet eset;
            int i = 0;
            for (const auto& entry : Entries) {
                if (s & (1 << i)) {
                    eset.Entries.insert(entry);
                }
                ++i;
            }
            if (eset.Entries.size() == 1) {
                std::string table_name = eset.Entries.begin()->TableName;
                eset.Entries.clear();
                eset.Entries.insert({table_name, ""});
            }
            subset.push_back(eset);
        }
    }

    void GetAllSubsetLimitSize(std::vector<EqualSet>& subset, size_t sizeLimit) const {
        subset.clear();
        for (int s = 0; s < 1 << Entries.size(); ++s) {
            EqualSet eset;
            int i = 0;
            for (const auto& entry : Entries) {
                if (s & (1 << i)) {
                    eset.Entries.insert(entry);
                }
                ++i;
            }
            if (eset.Entries.size() > sizeLimit) {
                continue;
            }
            if (eset.Entries.size() == 1) {
                std::string table_name = eset.Entries.begin()->TableName;
                eset.Entries.clear();
                eset.Entries.insert({table_name, ""});
            }
            subset.push_back(eset);
        }
    }

    void Split(std::vector<EqualSet>& subset, int maxSize) const {
        subset.clear();
        // Split in order by maxSize
        // For now, try to avoid splitting size-1 sets
        // TODO-STARCE: optimize after handling size-1 sets
        if (maxSize < 3) {
            throw std::runtime_error("maxSize must be at least 3");
        }
        int remain = Entries.size();
        for (auto it = Entries.begin(); it != Entries.end(); ) {
            EqualSet eset;
            if (remain - maxSize == 1) {
                // For now, try to avoid splitting size-1 sets
                for (int i = 0; i < maxSize - 1 && it != Entries.end(); ++i, ++it) {
                    eset.Entries.insert(*it);
                }
                remain -= maxSize - 1;
            } else {
                for (int i = 0; i < maxSize && it != Entries.end(); ++i, ++it) {
                    eset.Entries.insert(*it);
                }
                remain -= maxSize;
            }
            if (eset.Entries.size() == 1) {
                std::string table_name = eset.Entries.begin()->TableName;
                eset.Entries.clear();
                eset.Entries.insert({table_name, ""});
            }
            subset.push_back(eset);
        }
    }

    // bool CanMerge(const EqualSet& other) const
    // {
    //     int count = 0;
    //     for (const auto& entry : Entries) {
    //         if (other.Entries.find(entry) != other.Entries.end()) {
    //             ++count;
    //             if (count > 1) {
    //                 return false;
    //             }
    //         }
    //     }
    //     return count == 1;
    // }

    // std::string GetCommonTable(const EqualSet &other) const
    // {
    //     for (const auto& entry : Entries) {
    //         if (other.Entries.find(entry) != other.Entries.end()) {
    //             return entry.TableName;
    //         }
    //     }
    // }

    // void Merge(const EqualSet &other)
    // {
    //     Entries.insert(other.Entries.begin(), other.Entries.end());
    // }

    std::vector<Table> GetTableList() const
    {
        std::vector<Table> tables;
        for (const auto& entry : Entries) {
            tables.push_back(entry.TableName);
        }
        return tables;
    }

    size_t MemoryUsage() const
    {
        static constexpr size_t kSetNodeOverhead = 40;
        size_t total = sizeof(EqualSet);
        for (const auto &entry : Entries) {
            total += kSetNodeOverhead;
            total += sizeof(entry.TableName) + entry.TableName.capacity() + 1;
            total += sizeof(entry.ColumnName) + entry.ColumnName.capacity() + 1;
        }
        return total;
    }
};

} // namespace starce

#endif // INCLUDE_STARCE_EQUALSET_HPP_