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
    std::string TableName;  // 表名
    std::string ColumnName; // 列名

    // 默认构造函数
    TableColumn() = default;

    // 带参构造函数
    TableColumn(const std::string& tableName, const std::string& columnName)
        : TableName(tableName), ColumnName(columnName) {}

    // 序列化方法：将对象转换为 JSON 字符串
    std::string serialize() const {
        json j = {
            {"TableName", TableName},
            {"ColumnName", ColumnName}
        };
        return j.dump(); // 将 JSON 对象转换为字符串
    }

    // 反序列化方法：从 JSON 字符串转换为对象
    void deserialize(const std::string& jsonStr) {
        json j = json::parse(jsonStr); // 将字符串解析为 JSON 对象
        TableName = j.at("TableName").get<std::string>();
        ColumnName = j.at("ColumnName").get<std::string>();
    }

    // 重载比较运算符
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
    // 序列化方法：将对象转换为 JSON 字符串
    std::string serialize() const {
        return serialize_to_json().dump(); // 将 JSON 对象转换为字符串
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

    // 反序列化方法：从 JSON 字符串转换为对象
    void deserialize(const std::string& jsonStr) {
        json j = json::parse(jsonStr); // 将字符串解析为 JSON 对象
        deserialize(j);
    }

    // 反序列化方法：从 JSON 字符串转换为对象
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

    // 重载比较运算符
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
        // 以maxSize的大小拆分按顺序拆分
        // 暂时尽量不分割size为1的集合
        // TODO-STARCE 搞定size为1的集合后优化
        if (maxSize < 3) {
            throw std::runtime_error("maxSize must be at least 3");
        }
        int remain = Entries.size();
        for (auto it = Entries.begin(); it != Entries.end(); ) {
            EqualSet eset;
            if (remain - maxSize == 1) {
                // 暂时尽量不分割size为1的集合
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