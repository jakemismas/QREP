/*
 * Photo surface types (S6, issue #46; C1a, issue #146). The state modules
 * declare each of these once; the shell and the tests import them from here.
 * The hooks live with their state: usePhoto and useUncertainty in
 * state/photo.tsx, useRoundTrip in state/pattern.tsx.
 */
export type { PhotoScreen } from "../state/photoFlow";
export type { PhotoApi, PhotoResult, UncertaintyApi } from "../state/photo";
export type { RoundTripApi, RoundTripReport } from "../state/pattern";
