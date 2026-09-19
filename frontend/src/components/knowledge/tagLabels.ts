import type { ObjectType, RequestType } from '../../types/enums'

/** 中文名来自 docs/tag-taxonomy.json 的 object_types / request_types。 */
const OBJECT_TYPE_NAMES: Record<ObjectType, string> = {
  hardware: '硬件设备',
  software: '软件与操作系统',
  account: '账号与身份认证',
  network: '网络与远程接入',
  resource: '业务系统与共享资源',
}

const REQUEST_TYPE_NAMES: Record<RequestType, string> = {
  troubleshooting: '故障与异常排查',
  maintenance: '报修与维护服务',
  resource_request: '资源申请与变更',
  permission_request: '权限开通与调整',
  usage_guidance: '操作与配置指导',
  policy_process: '制度与流程说明',
}

export function objectTypeName(code: ObjectType): string {
  return OBJECT_TYPE_NAMES[code] ?? code
}

export function requestTypeName(code: RequestType): string {
  return REQUEST_TYPE_NAMES[code] ?? code
}
