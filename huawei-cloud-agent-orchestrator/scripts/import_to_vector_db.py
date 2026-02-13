#!/usr/bin/env python3
"""
将华为云服务操作导入到向量数据库
从服务注册表读取操作信息并构建详细的文档用于向量存储
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.huawei_cloud_service_registry import get_registry
from utils.vector_store import get_vector_store
from utils.logger import get_logger

logger = get_logger(__name__)


# 操作参数定义 - 基于华为云SDK API文档
# 这里定义了每个操作的输入参数和输出参数
OPERATION_DEFINITIONS = {
    # =============== ECS ===============
    "ecs:create_servers": {
        "description": "创建一台或多台弹性云服务器。支持指定镜像、规格、网络等参数",
        "input_params": {
            "server": {
                "type": "object",
                "description": "云服务器配置信息"
            },
            "server.name": {
                "type": "string",
                "description": "云服务器名称"
            },
            "server.flavorRef": {
                "type": "string",
                "description": "规格ID或规格名称，如 s6.large.2"
            },
            "server.imageRef": {
                "type": "string",
                "description": "镜像ID"
            },
            "server.vpcid": {
                "type": "string",
                "description": "虚拟私有云ID"
            },
            "server.nics": {
                "type": "array",
                "description": "网卡信息列表"
            },
            "server.nics[].subnet_id": {
                "type": "string",
                "description": "子网ID"
            },
            "server.root_volume": {
                "type": "object",
                "description": "系统盘信息"
            },
            "server.root_volume.volume_type": {
                "type": "string",
                "description": "云硬盘类型，如 SATA, SAS, SSD"
            },
            "server.root_volume.size": {
                "type": "integer",
                "description": "系统盘大小，单位为GB"
            },
            "server.adminPass": {
                "type": "string",
                "description": "管理员密码"
            },
            "server.key_name": {
                "type": "string",
                "description": "密钥对名称"
            },
            "count": {
                "type": "integer",
                "description": "创建的云服务器数量，默认为1"
            }
        },
        "output_params": {
            "serverIds": {
                "type": "array",
                "description": "创建成功的云服务器ID列表"
            },
            "job_id": {
                "type": "string",
                "description": "任务ID，用于查询创建进度"
            }
        }
    },
    "ecs:list_servers": {
        "description": "查询弹性云服务器列表。支持按名称、状态、规格等条件过滤",
        "input_params": {
            "limit": {
                "type": "integer",
                "description": "每页显示数量，默认20，最大100"
            },
            "offset": {
                "type": "integer",
                "description": "偏移量，从0开始"
            },
            "name": {
                "type": "string",
                "description": "云服务器名称，支持模糊查询"
            },
            "status": {
                "type": "string",
                "description": "云服务器状态，如 ACTIVE, BUILD, SHUTOFF"
            },
            "flavor": {
                "type": "string",
                "description": "规格名称"
            }
        },
        "output_params": {
            "servers": {
                "type": "array",
                "description": "云服务器列表"
            },
            "servers[].id": {
                "type": "string",
                "description": "云服务器ID"
            },
            "servers[].name": {
                "type": "string",
                "description": "云服务器名称"
            },
            "servers[].status": {
                "type": "string",
                "description": "云服务器状态"
            },
            "servers[].flavor": {
                "type": "object",
                "description": "规格信息"
            },
            "servers[].addresses": {
                "type": "object",
                "description": "网络地址信息"
            },
            "total_count": {
                "type": "integer",
                "description": "云服务器总数"
            }
        }
    },
    "ecs:get_server": {
        "description": "根据云服务器ID查询详细信息",
        "input_params": {
            "server_id": {
                "type": "string",
                "description": "云服务器ID",
                "required": True
            }
        },
        "output_params": {
            "server": {
                "type": "object",
                "description": "云服务器详细信息"
            },
            "server.id": {
                "type": "string",
                "description": "云服务器ID"
            },
            "server.name": {
                "type": "string",
                "description": "云服务器名称"
            },
            "server.status": {
                "type": "string",
                "description": "云服务器状态"
            },
            "server.flavor": {
                "type": "object",
                "description": "规格信息"
            },
            "server.image": {
                "type": "object",
                "description": "镜像信息"
            },
            "server.volumes_attached": {
                "type": "array",
                "description": "挂载的云硬盘列表"
            }
        }
    },
    "ecs:start_server": {
        "description": "启动已停止的云服务器",
        "input_params": {
            "server_id": {
                "type": "string",
                "description": "云服务器ID",
                "required": True
            }
        },
        "output_params": {
            "job_id": {
                "type": "string",
                "description": "任务ID，用于查询启动进度"
            }
        }
    },
    "ecs:stop_server": {
        "description": "关闭运行中的云服务器",
        "input_params": {
            "server_id": {
                "type": "string",
                "description": "云服务器ID",
                "required": True
            },
            "type": {
                "type": "string",
                "description": "关机类型：SOFT正常关机，HARD强制关机"
            }
        },
        "output_params": {
            "job_id": {
                "type": "string",
                "description": "任务ID，用于查询关机进度"
            }
        }
    },
    "ecs:reboot_server": {
        "description": "重启云服务器",
        "input_params": {
            "server_id": {
                "type": "string",
                "description": "云服务器ID",
                "required": True
            },
            "type": {
                "type": "string",
                "description": "重启类型：SOFT正常重启，HARD强制重启"
            }
        },
        "output_params": {
            "job_id": {
                "type": "string",
                "description": "任务ID，用于查询重启进度"
            }
        }
    },
    "ecs:delete_servers": {
        "description": "删除一台或多台云服务器。删除后无法恢复",
        "input_params": {
            "servers": {
                "type": "array",
                "description": "云服务器ID列表"
            },
            "delete_publicip": {
                "type": "boolean",
                "description": "是否同时删除弹性公网IP"
            },
            "delete_volume": {
                "type": "boolean",
                "description": "是否同时删除挂载的数据盘"
            }
        },
        "output_params": {
            "job_id": {
                "type": "string",
                "description": "任务ID，用于查询删除进度"
            }
        }
    },

    # =============== VPC ===============
    "vpc:create_vpc": {
        "description": "创建虚拟私有云VPC，提供隔离的网络环境",
        "input_params": {
            "vpc": {
                "type": "object",
                "description": "VPC配置信息"
            },
            "vpc.name": {
                "type": "string",
                "description": "VPC名称",
                "required": True
            },
            "vpc.cidr": {
                "type": "string",
                "description": "VPC的网段，如 192.168.0.0/16"
            },
            "enterprise_project_id": {
                "type": "string",
                "description": "企业项目ID"
            }
        },
        "output_params": {
            "vpc": {
                "type": "object",
                "description": "创建的VPC信息"
            },
            "vpc.id": {
                "type": "string",
                "description": "VPC ID"
            },
            "vpc.name": {
                "type": "string",
                "description": "VPC名称"
            },
            "vpc.cidr": {
                "type": "string",
                "description": "VPC网段"
            },
            "vpc.status": {
                "type": "string",
                "description": "VPC状态"
            }
        }
    },
    "vpc:list_vpcs": {
        "description": "查询虚拟私有云VPC列表",
        "input_params": {
            "limit": {
                "type": "integer",
                "description": "每页显示数量"
            },
            "offset": {
                "type": "integer",
                "description": "偏移量"
            },
            "id": {
                "type": "string",
                "description": "VPC ID"
            },
            "name": {
                "type": "string",
                "description": "VPC名称，支持模糊查询"
            },
            "cidr": {
                "type": "string",
                "description": "VPC网段"
            }
        },
        "output_params": {
            "vpcs": {
                "type": "array",
                "description": "VPC列表"
            },
            "vpcs[].id": {
                "type": "string",
                "description": "VPC ID"
            },
            "vpcs[].name": {
                "type": "string",
                "description": "VPC名称"
            },
            "vpcs[].cidr": {
                "type": "string",
                "description": "VPC网段"
            },
            "vpcs[].status": {
                "type": "string",
                "description": "VPC状态"
            },
            "total_count": {
                "type": "integer",
                "description": "VPC总数"
            }
        }
    },
    "vpc:create_subnet": {
        "description": "在VPC中创建子网，用于分配云服务器、负载均衡等资源的网络地址",
        "input_params": {
            "subnet": {
                "type": "object",
                "description": "子网配置信息"
            },
            "subnet.name": {
                "type": "string",
                "description": "子网名称",
                "required": True
            },
            "subnet.vpc_id": {
                "type": "string",
                "description": "VPC ID",
                "required": True
            },
            "subnet.cidr": {
                "type": "string",
                "description": "子网网段，必须在VPC网段范围内"
            },
            "subnet.gateway_ip": {
                "type": "string",
                "description": "子网网关地址"
            },
            "subnet.dhcp_enable": {
                "type": "boolean",
                "description": "是否开启DHCP"
            },
            "subnet.primary_dns": {
                "type": "string",
                "description": "主DNS服务器地址"
            },
            "subnet.secondary_dns": {
                "type": "string",
                "description": "备DNS服务器地址"
            }
        },
        "output_params": {
            "subnet": {
                "type": "object",
                "description": "创建的子网信息"
            },
            "subnet.id": {
                "type": "string",
                "description": "子网ID"
            },
            "subnet.name": {
                "type": "string",
                "description": "子网名称"
            },
            "subnet.cidr": {
                "type": "string",
                "description": "子网网段"
            },
            "subnet.vpc_id": {
                "type": "string",
                "description": "VPC ID"
            },
            "subnet.status": {
                "type": "string",
                "description": "子网状态"
            }
        }
    },
    "vpc:create_security_group": {
        "description": "创建安全组，用于设置网络访问控制规则",
        "input_params": {
            "security_group": {
                "type": "object",
                "description": "安全组配置信息"
            },
            "security_group.name": {
                "type": "string",
                "description": "安全组名称",
                "required": True
            },
            "security_group.vpc_id": {
                "type": "string",
                "description": "VPC ID",
                "required": True
            },
            "security_group.description": {
                "type": "string",
                "description": "安全组描述"
            }
        },
        "output_params": {
            "security_group": {
                "type": "object",
                "description": "创建的安全组信息"
            },
            "security_group.id": {
                "type": "string",
                "description": "安全组ID"
            },
            "security_group.name": {
                "type": "string",
                "description": "安全组名称"
            },
            "security_group.description": {
                "type": "string",
                "description": "安全组描述"
            },
            "security_group.security_group_rules": {
                "type": "array",
                "description": "安全组规则列表"
            }
        }
    },

    # =============== RDS ===============
    "rds:create_instance": {
        "description": "创建云数据库实例，支持MySQL、PostgreSQL、SQL Server等多种数据库",
        "input_params": {
            "name": {
                "type": "string",
                "description": "实例名称",
                "required": True
            },
            "datastore": {
                "type": "object",
                "description": "数据库配置"
            },
            "datastore.type": {
                "type": "string",
                "description": "数据库类型，如 MySQL, PostgreSQL, SQLServer"
            },
            "datastore.version": {
                "type": "string",
                "description": "数据库版本，如 8.0, 5.7"
            },
            "flavor_ref": {
                "type": "string",
                "description": "规格码，如 rds.mysql.s1.large"
            },
            "volume": {
                "type": "object",
                "description": "存储配置"
            },
            "volume.type": {
                "type": "string",
                "description": "磁盘类型，如 COMMON, ULTRAHIGH"
            },
            "volume.size": {
                "type": "integer",
                "description": "存储大小，单位GB"
            },
            "vpc_id": {
                "type": "string",
                "description": "VPC ID"
            },
            "subnet_id": {
                "type": "string",
                "description": "子网ID"
            },
            "password": {
                "type": "string",
                "description": "数据库管理员密码"
            },
            "port": {
                "type": "integer",
                "description": "数据库端口"
            },
            "ha": {
                "type": "object",
                "description": "高可用配置"
            },
            "ha.mode": {
                "type": "string",
                "description": "高可用模式，如 Ha, Standalone"
            },
            "ha.replication_mode": {
                "type": "string",
                "description": "复制模式，如 semisync, async"
            }
        },
        "output_params": {
            "instance": {
                "type": "object",
                "description": "创建的实例信息"
            },
            "instance.id": {
                "type": "string",
                "description": "实例ID"
            },
            "instance.name": {
                "type": "string",
                "description": "实例名称"
            },
            "instance.status": {
                "type": "string",
                "description": "实例状态"
            },
            "instance.port": {
                "type": "integer",
                "description": "端口号"
            },
            "job_id": {
                "type": "string",
                "description": "任务ID"
            }
        }
    },
    "rds:list_instances": {
        "description": "查询云数据库实例列表",
        "input_params": {
            "limit": {
                "type": "integer",
                "description": "每页显示数量"
            },
            "offset": {
                "type": "integer",
                "description": "偏移量"
            },
            "id": {
                "type": "string",
                "description": "实例ID"
            },
            "name": {
                "type": "string",
                "description": "实例名称，支持模糊查询"
            },
            "type": {
                "type": "string",
                "description": "实例类型"
            },
            "datastore_type": {
                "type": "string",
                "description": "数据库类型"
            },
            "vpc_id": {
                "type": "string",
                "description": "VPC ID"
            }
        },
        "output_params": {
            "instances": {
                "type": "array",
                "description": "实例列表"
            },
            "instances[].id": {
                "type": "string",
                "description": "实例ID"
            },
            "instances[].name": {
                "type": "string",
                "description": "实例名称"
            },
            "instances[].status": {
                "type": "string",
                "description": "实例状态"
            },
            "instances[].datastore": {
                "type": "object",
                "description": "数据库信息"
            },
            "instances[].flavor_ref": {
                "type": "string",
                "description": "规格码"
            },
            "total_count": {
                "type": "integer",
                "description": "实例总数"
            }
        }
    },
    "rds:create_backup": {
        "description": "创建数据库手动备份",
        "input_params": {
            "instance_id": {
                "type": "string",
                "description": "实例ID",
                "required": True
            },
            "name": {
                "type": "string",
                "description": "备份名称"
            },
            "description": {
                "type": "string",
                "description": "备份描述"
            }
        },
        "output_params": {
            "backup": {
                "type": "object",
                "description": "备份信息"
            },
            "backup.id": {
                "type": "string",
                "description": "备份ID"
            },
            "backup.name": {
                "type": "string",
                "description": "备份名称"
            },
            "backup.size": {
                "type": "integer",
                "description": "备份大小"
            },
            "backup.begin_time": {
                "type": "string",
                "description": "备份开始时间"
            },
            "backup.status": {
                "type": "string",
                "description": "备份状态"
            }
        }
    },
    "rds:restore_instance": {
        "description": "恢复数据库到指定备份或时间点",
        "input_params": {
            "instance_id": {
                "type": "string",
                "description": "实例ID",
                "required": True
            },
            "restore_time": {
                "type": "string",
                "description": "恢复到的时间点"
            },
            "backup_id": {
                "type": "string",
                "description": "用于恢复的备份ID"
            }
        },
        "output_params": {
            "job_id": {
                "type": "string",
                "description": "任务ID，用于查询恢复进度"
            }
        }
    },

    # =============== OBS ===============
    "obs:create_bucket": {
        "description": "创建对象存储桶，用于存储文件、图片、视频等数据",
        "input_params": {
            "Bucket": {
                "type": "string",
                "description": "桶名称",
                "required": True
            },
            "ACL": {
                "type": "string",
                "description": "桶访问控制策略"
            },
            "Location": {
                "type": "string",
                "description": "区域，如 cn-north-4"
            },
            "StorageClass": {
                "type": "string",
                "description": "存储类型：STANDARD标准存储，WARM低频访问，COLD归档存储"
            },
            "IsEncrypted": {
                "type": "boolean",
                "description": "是否开启服务端加密"
            }
        },
        "output_params": {
            "Location": {
                "type": "string",
                "description": "桶所在的区域"
            }
        }
    },
    "obs:list_buckets": {
        "description": "查询对象存储桶列表",
        "input_params": {
            "Max-keys": {
                "type": "integer",
                "description": "最大返回数量，默认100"
            },
            "Marker": {
                "type": "string",
                "description": "分页标记"
            }
        },
        "output_params": {
            "Buckets": {
                "type": "array",
                "description": "桶列表"
            },
            "Buckets[].Name": {
                "type": "string",
                "description": "桶名称"
            },
            "Buckets[].CreationDate": {
                "type": "string",
                "description": "创建时间"
            },
            "Buckets[].Location": {
                "type": "string",
                "description": "区域"
            },
            "Owner": {
                "type": "object",
                "description": "桶所有者信息"
            }
        }
    },
    "obs:put_object": {
        "description": "上传文件到对象存储桶",
        "input_params": {
            "Bucket": {
                "type": "string",
                "description": "桶名称",
                "required": True
            },
            "Key": {
                "type": "string",
                "description": "对象键（文件名）",
                "required": True
            },
            "Body": {
                "type": "binary",
                "description": "文件内容"
            },
            "ContentType": {
                "type": "string",
                "description": "内容类型，如 application/json, image/png"
            },
            "Metadata": {
                "type": "object",
                "description": "自定义元数据"
            },
            "StorageClass": {
                "type": "string",
                "description": "存储类型"
            }
        },
        "output_params": {
            "ETag": {
                "type": "string",
                "description": "对象的ETag值"
            },
            "VersionId": {
                "type": "string",
                "description": "版本ID（如果开启了版本控制）"
            }
        }
    },
    "obs:get_object": {
        "description": "从对象存储桶下载文件",
        "input_params": {
            "Bucket": {
                "type": "string",
                "description": "桶名称",
                "required": True
            },
            "Key": {
                "type": "string",
                "description": "对象键（文件名）",
                "required": True
            },
            "VersionId": {
                "type": "string",
                "description": "版本ID"
            },
            "Range": {
                "type": "string",
                "description": "字节范围，用于断点续传"
            }
        },
        "output_params": {
            "Body": {
                "type": "binary",
                "description": "文件内容"
            },
            "Metadata": {
                "type": "object",
                "description": "对象元数据"
            },
            "ContentType": {
                "type": "string",
                "description": "内容类型"
            },
            "ContentLength": {
                "type": "integer",
                "description": "内容长度"
            },
            "ETag": {
                "type": "string",
                "description": "ETag值"
            }
        }
    },
    "obs:delete_object": {
        "description": "从对象存储桶删除文件",
        "input_params": {
            "Bucket": {
                "type": "string",
                "description": "桶名称",
                "required": True
            },
            "Key": {
                "type": "string",
                "description": "对象键（文件名）",
                "required": True
            },
            "VersionId": {
                "type": "string",
                "description": "版本ID"
            }
        },
        "output_params": {
            "success": {
                "type": "boolean",
                "description": "是否删除成功"
            }
        }
    },

    # =============== CCE ===============
    "cce:create_cluster": {
        "description": "创建云容器引擎集群，用于部署和管理容器化应用",
        "input_params": {
            "cluster": {
                "type": "object",
                "description": "集群配置"
            },
            "cluster.name": {
                "type": "string",
                "description": "集群名称",
                "required": True
            },
            "cluster.version": {
                "type": "string",
                "description": "集群版本，如 v1.27"
            },
            "cluster.flavor": {
                "type": "string",
                "description": "集群规格，如 cce.s1.small"
            },
            "cluster.vpc": {
                "type": "string",
                "description": "VPC ID",
                "required": True
            },
            "cluster.subnet": {
                "type": "string",
                "description": "子网ID"
            },
            "cluster.container_network_type": {
                "type": "string",
                "description": "容器网络类型，如 overlay_l2, vpc-router"
            },
            "cluster.kube_proxy_mode": {
                "type": "string",
                "description": "服务转发模式，如 iptables, ipvs"
            },
            "cluster.service_network_cidr": {
                "type": "string",
                "description": "服务网段"
            }
        },
        "output_params": {
            "cluster": {
                "type": "object",
                "description": "创建的集群信息"
            },
            "cluster.id": {
                "type": "string",
                "description": "集群ID"
            },
            "cluster.name": {
                "type": "string",
                "description": "集群名称"
            },
            "cluster.status": {
                "type": "string",
                "description": "集群状态"
            },
            "cluster.kubeconfig": {
                "type": "string",
                "description": "Kubeconfig配置"
            }
        }
    },
    "cce:add_node": {
        "description": "向集群添加工作节点",
        "input_params": {
            "cluster_id": {
                "type": "string",
                "description": "集群ID",
                "required": True
            },
            "node": {
                "type": "object",
                "description": "节点配置"
            },
            "node.name": {
                "type": "string",
                "description": "节点名称"
            },
            "node.flavor": {
                "type": "string",
                "description": "规格"
            },
            "node.os": {
                "type": "string",
                "description": "操作系统类型，如 Linux, Windows"
            },
            "node.root_volume": {
                "type": "object",
                "description": "系统盘配置"
            },
            "node.data_volumes": {
                "type": "array",
                "description": "数据盘配置列表"
            }
        },
        "output_params": {
            "job_id": {
                "type": "string",
                "description": "任务ID"
            },
            "node_id": {
                "type": "string",
                "description": "节点ID"
            }
        }
    },

    # =============== ELB ===============
    "elb:create_loadbalancer": {
        "description": "创建弹性负载均衡器，用于分发流量到多个后端服务器",
        "input_params": {
            "loadbalancer": {
                "type": "object",
                "description": "负载均衡器配置"
            },
            "loadbalancer.name": {
                "type": "string",
                "description": "负载均衡器名称",
                "required": True
            },
            "loadbalancer.vpc_id": {
                "type": "string",
                "description": "VPC ID"
            },
            "loadbalancer.availability_zone": {
                "type": "array",
                "description": "可用区列表"
            },
            "loadbalancer.ip_target_enable": {
                "type": "boolean",
                "description": "是否开启跨VPC后端转发"
            },
            "loadbalancer.bandwidth": {
                "type": "integer",
                "description": "带宽大小"
            },
            "loadbalancer.traffic_ip": {
                "type": "array",
                "description": "IP地址列表"
            }
        },
        "output_params": {
            "loadbalancer": {
                "type": "object",
                "description": "创建的负载均衡器信息"
            },
            "loadbalancer.id": {
                "type": "string",
                "description": "负载均衡器ID"
            },
            "loadbalancer.name": {
                "type": "string",
                "description": "负载均衡器名称"
            },
            "loadbalancer.status": {
                "type": "string",
                "description": "状态"
            },
            "loadbalancer.vip_address": {
                "type": "string",
                "description": "VIP地址"
            }
        }
    },
    "elb:create_listener": {
        "description": "创建监听器，用于监听特定端口的流量",
        "input_params": {
            "listener": {
                "type": "object",
                "description": "监听器配置"
            },
            "listener.name": {
                "type": "string",
                "description": "监听器名称",
                "required": True
            },
            "listener.loadbalancer_id": {
                "type": "string",
                "description": "负载均衡器ID",
                "required": True
            },
            "listener.protocol": {
                "type": "string",
                "description": "协议，如 TCP, UDP, HTTP, HTTPS"
            },
            "listener.protocol_port": {
                "type": "integer",
                "description": "监听端口"
            },
            "listener.default_pool_id": {
                "type": "string",
                "description": "默认后端服务器组ID"
            },
            "listener.default_tls_container_ref": {
                "type": "string",
                "description": "默认证书ID（HTTPS协议）"
            }
        },
        "output_params": {
            "listener": {
                "type": "object",
                "description": "创建的监听器信息"
            },
            "listener.id": {
                "type": "string",
                "description": "监听器ID"
            },
            "listener.name": {
                "type": "string",
                "description": "监听器名称"
            },
            "listener.status": {
                "type": "string",
                "description": "状态"
            }
        }
    }
}


def build_operation_operations_list():
    """构建完整的操作列表"""
    registry = get_registry()
    all_services = registry.get_all_services()

    operations = []

    for service_name, service_info in all_services.items():
        for operation_name in service_info.common_operations:
            op_key = f"{service_name}:{operation_name}"

            # 检查是否有详细定义
            if op_key in OPERATION_DEFINITIONS:
                definition = OPERATION_DEFINITIONS[op_key]
            else:
                # 使用通用描述
                definition = {
                    "description": f"{service_info.description}的{operation_name}操作",
                    "input_params": {},
                    "output_params": {}
                }

            operations.append({
                "operation_id": op_key,
                "service_name": service_name,
                "operation_name": operation_name,
                "description": definition["description"],
                "input_params": definition["input_params"],
                "output_params": definition["output_params"],
                "metadata": {
                    "service_description": service_info.description,
                    "module_name": service_info.module_name,
                    "client_class": service_info.client_class
                }
            })

    return operations


def import_to_vector_db(clear_existing=False):
    """
    导入操作到向量数据库

    Args:
        clear_existing: 是否清空已有数据
    """
    logger.info("开始导入华为云服务操作到向量数据库...")

    # 获取向量存储
    vector_store = get_vector_store()

    # 清空已有数据
    if clear_existing:
        logger.info("清空已有数据...")
        if vector_store.clear_all():
            logger.info("清空完成")
        else:
            logger.error("清空失败")
            return False

    # 构建操作列表
    operations = build_operation_operations_list()
    logger.info(f"构建了 {len(operations)} 个操作")

    # 批量添加
    success_count = vector_store.batch_add_operations(operations)

    # 获取统计信息
    stats = vector_store.get_stats()

    logger.info("=" * 80)
    logger.info("导入完成！")
    logger.info(f"成功导入: {success_count}/{len(operations)}")
    logger.info(f"总操作数: {stats['total_operations']}")
    logger.info(f"服务数量: {stats['total_services']}")
    logger.info("=" * 80)

    return success_count > 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="导入华为云服务操作到向量数据库")
    parser.add_argument("--clear", action="store_true", help="清空已有数据后导入")

    args = parser.parse_args()

    success = import_to_vector_db(clear_existing=args.clear)

    sys.exit(0 if success else 1)
