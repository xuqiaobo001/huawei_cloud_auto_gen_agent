from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from uuid import uuid4


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class TaskType(Enum):
    """任务类型枚举"""
    HUAWEICLOUD_API = "huaweicloud_api"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    WAIT = "wait"
    PARALLEL = "parallel"
    SCRIPT = "script"


class WorkflowStatus(Enum):
    """工作流状态枚举"""
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务定义"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: TaskType = TaskType.HUAWEICLOUD_API
    description: str = ""
    service: Optional[str] = None
    operation: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    output: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['type'] = self.type.value
        return data


@dataclass
class Workflow:
    """工作流定义"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0"
    trigger: Optional[Dict[str, Any]] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    tasks: List[Task] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def validate(self) -> List[str]:
        errors = []
        if not self.tasks:
            errors.append("工作流必须至少包含一个任务")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['tasks'] = [task.to_dict() for task in self.tasks]
        return data


# 参数模板
PARAMETER_TEMPLATES = {
    "create_ecs": {
        "server": {
            "name": "{{ instance_name }}",
            "flavorRef": "{{ flavor }}",
            "imageRef": "{{ image_id }}",
            "vpcid": "{{ vpc_id }}",
            "nics": [{
                "subnet_id": "{{ subnet_id }}"
            }]
        },
        "count": 1
    },
    "create_vpc": {
        "name": "{{ vpc_name }}",
        "cidr": "{{ cidr_block }}"
    },
    "create_subnet": {
        "name": "{{ subnet_name }}",
        "vpc_id": "{{ vpc_id }}",
        "cidr": "{{ cidr_block }}",
        "gateway_ip": "{{ gateway_ip }}"
    },
    "create_rds_instance": {
        "name": "{{ db_name }}",
        "datastore": {
            "type": "{{ db_type }}",
            "version": "{{ db_version }}"
        },
        "flavor_ref": "{{ flavor }}",
        "volume": {
            "type": "{{ volume_type }}",
            "size": "{{ volume_size }}"
        },
        "vpc_id": "{{ vpc_id }}",
        "subnet_id": "{{ subnet_id }}",
        "db": {
            "password": "{{ db_password }}",
            "port": "{{ db_port }}"
        }
    },
    "create_security_group": {
        "name": "{{ sg_name }}",
        "vpc_id": "{{ vpc_id }}",
        "description": "{{ description }}"
    },
    "create_security_group_rule": {
        "security_group_id": "{{ security_group_id }}",
        "direction": "{{ direction }}",
        "ethertype": "IPv4",
        "protocol": "{{ protocol }}",
        "port_range_min": "{{ port_min }}",
        "port_range_max": "{{ port_max }}",
        "remote_ip_prefix": "{{ remote_ip_prefix }}"
    },
    "create_loadbalancer": {
        "name": "{{ elb_name }}",
        "vip_subnet_cidr_id": "{{ subnet_id }}",
        "vpc_id": "{{ vpc_id }}",
        "description": "{{ description }}"
    },
    "create_listener": {
        "name": "{{ listener_name }}",
        "protocol": "{{ protocol }}",
        "protocol_port": "{{ port }}",
        "loadbalancer_id": "{{ loadbalancer_id }}"
    },
    "create_pool": {
        "name": "{{ pool_name }}",
        "protocol": "{{ protocol }}",
        "lb_algorithm": "{{ lb_algorithm }}",
        "listener_id": "{{ listener_id }}",
        "loadbalancer_id": "{{ loadbalancer_id }}"
    },
    "create_member": {
        "pool_id": "{{ pool_id }}",
        "address": "{{ member_address }}",
        "protocol_port": "{{ port }}",
        "subnet_cidr_id": "{{ subnet_id }}"
    },
    "create_publicip": {
        "publicip": {
            "type": "5_bgp"
        },
        "bandwidth": {
            "name": "{{ bandwidth_name }}",
            "size": "{{ bandwidth_size }}",
            "share_type": "PER",
            "charge_mode": "traffic"
        },
        "port_id": "{{ port_id }}"
    },
    "create_servers": {
        "server": {
            "name": "{{ server_name }}",
            "flavorRef": "{{ flavor }}",
            "imageRef": "{{ image_id }}",
            "vpcid": "{{ vpc_id }}",
            "nics": [{"subnet_id": "{{ subnet_id }}"}],
            "security_groups": [{"id": "{{ security_group_id }}"}]
        },
        "count": 1
    },
    "create_cluster": {
        "kind": "Cluster",
        "metadata": {"name": "{{ cluster_name }}"},
        "spec": {
            "flavor": "{{ cluster_flavor }}",
            "hostNetwork": {
                "vpc": "{{ vpc_id }}",
                "subnet": "{{ subnet_id }}"
            },
            "containerNetwork": {
                "mode": "overlay_l2"
            }
        }
    },
    "create_dcs_instance": {
        "name": "{{ instance_name }}",
        "engine": "Redis",
        "engine_version": "{{ engine_version }}",
        "capacity": "{{ capacity }}",
        "vpc_id": "{{ vpc_id }}",
        "subnet_id": "{{ subnet_id }}",
        "security_group_id": "{{ security_group_id }}",
        "spec_code": "{{ spec_code }}"
    },
    "create_alarm": {
        "alarm_name": "{{ alarm_name }}",
        "metric": {
            "namespace": "{{ namespace }}",
            "metric_name": "{{ metric_name }}",
            "dimensions": [{"name": "{{ dimension_name }}", "value": "{{ dimension_value }}"}]
        },
        "condition": {
            "comparison_operator": "{{ operator }}",
            "value": "{{ threshold }}",
            "period": "{{ period }}",
            "count": "{{ count }}"
        },
        "alarm_enabled": True
    },
    "create_waf_policy": {
        "name": "{{ policy_name }}"
    }
}
