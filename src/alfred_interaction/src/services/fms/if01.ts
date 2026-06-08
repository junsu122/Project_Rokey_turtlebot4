import { makeId } from '@/core/utils/id';

/**
 * IF-01 — 고객 요청 (Interaction → FMS). The kiosk (Interaction track) publishes
 * this once a destination is confirmed; the FMS plans assignment/handoff. Field
 * names are snake_case to match the wire contract in 인터페이스 정의서 v2.1 §2.
 */
export const IF_VERSION = '2.0';

export type If01RequestType = 'ESCORT' | 'CANCEL' | 'INTERACTING';

/** Drives the robot's motion params / arrival greeting (정의서 §2). */
export type CustomerProfile =
  | 'GENERAL'
  | 'ELDERLY'
  | 'FOREIGNER'
  | 'VISUALLY_IMPAIRED';

export interface If01Pose {
  x: number;
  y: number;
}

export interface If01Destination {
  poi_id: string;
  floor: number;
}

export interface If01Origin {
  floor: number;
  pose: If01Pose;
}

export interface If01Customer {
  customer_id: string;
  profile: CustomerProfile;
  language: string;
}

interface If01Base {
  msg_id: string;
  version: string;
  request_id: string;
  robot_id: string;
  timestamp: string;
}

/** IF-01 ESCORT — a confirmed customer escort request to a valid POI. */
export interface If01EscortRequest extends If01Base {
  request_type: 'ESCORT';
  destination: If01Destination;
  origin: If01Origin;
  customer: If01Customer;
}

/** IF-01 CANCEL — cancel a previously issued request (정의서 §7). */
export interface If01CancelRequest extends If01Base {
  request_type: 'CANCEL';
  target_request_id: string;
}

/**
 * IF-01 INTERACTING — a customer just started interacting with this kiosk
 * (patrol → home/voice via touch or the "hello Alfred" wake word). Lets the FMS
 * mark this robot busy before any destination is known. Same envelope as ESCORT
 * minus `destination` (none yet); `origin`/`customer` carry what we do know.
 */
export interface If01InteractingRequest extends If01Base {
  request_type: 'INTERACTING';
  origin: If01Origin;
  customer: If01Customer;
}

export type If01Request =
  | If01EscortRequest
  | If01CancelRequest
  | If01InteractingRequest;

export interface EscortRequestInput {
  robotId: string;
  destination: { poiId: string; floor: number };
  origin: If01Origin;
  customer: If01Customer;
}

export interface InteractingRequestInput {
  robotId: string;
  origin: If01Origin;
  customer: If01Customer;
}

/**
 * A fresh anonymous customer. `profile` is VISUALLY_IMPAIRED in the wake-word
 * voice (VI) mode, GENERAL otherwise; `language` is the user's UI language.
 */
export function defaultCustomer(
  profile: CustomerProfile = 'GENERAL',
  language = 'ko',
): If01Customer {
  return { customer_id: makeId('C'), profile, language };
}

/** Build an IF-01 ESCORT request for a confirmed destination. */
export function buildEscortRequest(
  input: EscortRequestInput,
): If01EscortRequest {
  return {
    msg_id: makeId('msg'),
    version: IF_VERSION,
    request_id: makeId('REQ'),
    robot_id: input.robotId,
    request_type: 'ESCORT',
    destination: {
      poi_id: input.destination.poiId,
      floor: input.destination.floor,
    },
    origin: input.origin,
    customer: input.customer,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Build an IF-01 INTERACTING notification for the moment a customer engages the
 * kiosk (leaves patrol). No destination yet — only robot/origin/customer.
 */
export function buildInteractingRequest(
  input: InteractingRequestInput,
): If01InteractingRequest {
  return {
    msg_id: makeId('msg'),
    version: IF_VERSION,
    request_id: makeId('REQ'),
    robot_id: input.robotId,
    request_type: 'INTERACTING',
    origin: input.origin,
    customer: input.customer,
    timestamp: new Date().toISOString(),
  };
}

/** Build an IF-01 CANCEL targeting a prior request. New request_id each time. */
export function buildCancelRequest(
  robotId: string,
  targetRequestId: string,
): If01CancelRequest {
  return {
    msg_id: makeId('msg'),
    version: IF_VERSION,
    request_id: makeId('REQ'),
    robot_id: robotId,
    request_type: 'CANCEL',
    target_request_id: targetRequestId,
    timestamp: new Date().toISOString(),
  };
}

/** ROS string types that carry the IF-01 JSON as text in their `data` field. */
const STRING_MSG_TYPES = new Set(['std_msgs/String', 'std_msgs/msg/String']);

/**
 * Shape the rosbridge `msg` payload for an IF-01 request given the topic's ROS
 * type. rosbridge can only publish to a topic whose message type it knows.
 *
 * - `std_msgs/String` (default): the whole request is JSON-serialized into
 *   `.data` — the universal "ship arbitrary JSON over ROS" form. The consumer
 *   does `json.loads(msg.data)`.
 * - any other (custom) type: the structured request is sent as-is, so its fields
 *   map 1:1 onto a matching .msg definition on the robot side.
 */
export function toRosPayload(request: If01Request, msgType: string): unknown {
  return STRING_MSG_TYPES.has(msgType)
    ? { data: JSON.stringify(request) }
    : request;
}
