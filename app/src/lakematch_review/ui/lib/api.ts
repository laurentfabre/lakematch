// Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.
import { useQuery, useSuspenseQuery, useMutation } from "@tanstack/react-query";
import type { UseQueryOptions, UseSuspenseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
export class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;
    constructor(status: number, statusText: string, body: unknown){
        super(`HTTP ${status}: ${statusText}`);
        this.name = "ApiError";
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}
export type CancelIn = {
    expected_revision: number;
    lease_token?: string | null;
    reason: string;
} & {
};
export type ClaimIn = {
    expected_revision: number;
    reason: string;
    seconds: number;
} & {
};
export type CreateTaskIn = {
    entity_ids: string[];
    evidence: Record<string, unknown>;
    kind: "merge" | "override" | "split_new" | "restore_merge";
    priority?: number;
    reason: string;
} & {
};
export type DemoAlternativeOut = {
    excluded: string | null;
    quality: number | null;
    source_id: string;
    source_key: string;
    value: string | null;
    verified: boolean | null;
    version: number;
} & {
};
export type DemoCatalogOut = {
    companies: DemoCompanyOut[];
    default_master_id: string;
    kind?: "synthetic_company_demo";
    publications: ("first" | "second")[];
} & {
};
export type DemoCompanyOut = {
    country: string;
    legal_name: string;
    master_id: string;
} & {
};
export type DemoComparedRecordOut = {
    deleted: boolean;
    source_id: string;
    source_key: string;
    version: number;
} & {
};
export type DemoComparisonDecisionOut = {
    auto_merge_eligible: false;
    reason: string;
    route: "review" | "exclude";
    rule_id: string;
    suggestion: "match" | "no_match" | "unsure" | "not_applicable";
} & {
};
export type DemoComparisonFieldOut = {
    comparison: "agree" | "differ" | "unavailable";
    left: DemoComparisonValueOut;
    name: "record_kind" | "legal_name" | "country" | "registration_id" | "address_line1" | "city" | "postal_code";
    raw_equal: boolean | null;
    right: DemoComparisonValueOut;
} & {
};
export type DemoComparisonOut = {
    algorithm: "company_pair_evidence_v2";
    decision: DemoComparisonDecisionOut;
    evidence_sha256: string;
    fields: DemoComparisonFieldOut[];
    implementation_sha256: string;
    pair_id: string;
    pair_origin: "explicit_comparison";
    probability: null;
    qualification: "development_preview_only";
    records: DemoComparedRecordOut[];
    rules: DemoComparisonRuleOut[];
    ruleset_id: string;
    ruleset_sha256: string;
    ruleset_version: number;
    schema_version: 2;
} & {
};
export type DemoComparisonRuleOut = {
    reason: string;
    rule_id: string;
    selected: boolean;
} & {
};
export type DemoComparisonValueOut = {
    normalized: string | null;
    state: "present" | "missing" | "null" | "blank" | "invalid_type" | "invalid_format" | "deleted";
    value: string | null;
} & {
};
export type DemoDetailOut = {
    as_of: string;
    entity: DemoEntityOut;
    kind?: "synthetic_company_demo";
    membership_basis?: "synthetic_fixture_truth";
    publication_id: "first" | "second";
    snapshot_sha256: string;
} & {
};
export type DemoEntityOut = {
    comparison: DemoComparisonOut;
    fields: DemoFieldOut[];
    identity_revision: number;
    master_id: string;
    policy_id: string;
    policy_sha256: string;
    policy_version: number;
    revision: number;
    sources: DemoSourceOut[];
    values: Record<string, string | null>;
} & {
};
export type DemoFieldOut = {
    alternatives: DemoAlternativeOut[];
    approved_by: string | null;
    conflicting_values: boolean;
    decision_id: string | null;
    decision_reason: string | null;
    name: string;
    reason: string;
    value: string | null;
    winner_source_id: string | null;
    winner_source_key: string | null;
    winner_version: number | null;
} & {
};
export type DemoSourceOut = {
    deleted: boolean;
    source_id: string;
    source_key: string;
    updated_at: string;
    values: Record<string, string | null>;
    version: number;
} & {
};
export interface EvaluationOut {
    context: string;
    model_version: string;
    precision: number;
    recall: number;
    sample_size: number;
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface LabelOut {
    a_id: string;
    b_id: string;
    label: number;
}
export type LeaseIn = {
    expected_revision: number;
    lease_token: string;
    reason: string;
} & {
};
export interface PairOut {
    a_id: string;
    b_id: string;
    impact?: number;
    left: Record<string, string | null>;
    llm_decision?: "match" | "no_match" | "unsure" | null;
    model_version: string;
    pair_id: string;
    probability: number;
    right: Record<string, string | null>;
    threshold: number;
}
export type ProposeIn = {
    evidence: Record<string, unknown>;
    expected_revision: number;
    lease_token: string;
    payload: Record<string, unknown>;
    reason: string;
    versions: Record<string, number>;
} & {
};
export type RenewIn = {
    expected_revision: number;
    lease_token: string;
    reason: string;
    seconds: number;
} & {
};
export type ReviewIn = {
    decision: "match" | "no_match" | "unsure";
    model_version: string;
    pair_id: string;
    reason: string;
    request_id: string;
} & {
};
export type ReviewOut = {
    a_id: string;
    b_id: string;
    decision: "match" | "no_match" | "unsure";
    model_version: string;
    pair_id: string;
    reason: string;
    request_id: string;
    reviewed_at: string;
    user: string;
} & {
};
export type RevisionIn = {
    expected_revision: number;
    reason: string;
} & {
};
export interface SessionOut {
    genie_enabled: boolean;
    storage: "sqlite" | "delta";
    user: string;
}
export interface SnapshotOut {
    excluded_unsure: number;
    label_set_sha256: string;
    labels: LabelOut[];
    reviews: ReviewOut[];
}
export interface StatsOut {
    evaluations: EvaluationOut[];
    llm_agreement: number | null;
    llm_compared: number;
    match: number;
    no_match: number;
    quarantine: number | null;
    queue_depth: number;
    reviewed: number;
    unsure: number;
}
export interface ValidationError {
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface GoldenDemoCatalogParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const goldenDemoCatalog = async (params?: GoldenDemoCatalogParams, options?: RequestInit): Promise<{
    data: DemoCatalogOut;
}> =>{
    const res = await fetch("/api/demo/golden-records", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const goldenDemoCatalogKey = (params?: GoldenDemoCatalogParams)=>{
    return [
        "/api/demo/golden-records",
        params
    ] as const;
};
export function useGoldenDemoCatalog<TData = {
    data: DemoCatalogOut;
}>(options?: {
    params?: GoldenDemoCatalogParams;
    query?: Omit<UseQueryOptions<{
        data: DemoCatalogOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: goldenDemoCatalogKey(options?.params),
        queryFn: ()=>goldenDemoCatalog(options?.params),
        ...options?.query
    });
}
export function useGoldenDemoCatalogSuspense<TData = {
    data: DemoCatalogOut;
}>(options?: {
    params?: GoldenDemoCatalogParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: DemoCatalogOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: goldenDemoCatalogKey(options?.params),
        queryFn: ()=>goldenDemoCatalog(options?.params),
        ...options?.query
    });
}
export interface GoldenDemoDetailParams {
    master_id: string;
    publication?: "first" | "second";
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const goldenDemoDetail = async (params: GoldenDemoDetailParams, options?: RequestInit): Promise<{
    data: DemoDetailOut;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.publication != null) searchParams.set("publication", String(params?.publication));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/demo/golden-records/${params.master_id}?${queryString}` : `/api/demo/golden-records/${params.master_id}`;
    const res = await fetch(url, {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const goldenDemoDetailKey = (params?: GoldenDemoDetailParams)=>{
    return [
        "/api/demo/golden-records/{master_id}",
        params
    ] as const;
};
export function useGoldenDemoDetail<TData = {
    data: DemoDetailOut;
}>(options: {
    params: GoldenDemoDetailParams;
    query?: Omit<UseQueryOptions<{
        data: DemoDetailOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: goldenDemoDetailKey(options.params),
        queryFn: ()=>goldenDemoDetail(options.params),
        ...options?.query
    });
}
export function useGoldenDemoDetailSuspense<TData = {
    data: DemoDetailOut;
}>(options: {
    params: GoldenDemoDetailParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: DemoDetailOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: goldenDemoDetailKey(options.params),
        queryFn: ()=>goldenDemoDetail(options.params),
        ...options?.query
    });
}
export interface ReviewQueueParams {
    limit?: number;
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const reviewQueue = async (params?: ReviewQueueParams, options?: RequestInit): Promise<{
    data: PairOut[];
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.limit != null) searchParams.set("limit", String(params?.limit));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/queue?${queryString}` : "/api/queue";
    const res = await fetch(url, {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const reviewQueueKey = (params?: ReviewQueueParams)=>{
    return [
        "/api/queue",
        params
    ] as const;
};
export function useReviewQueue<TData = {
    data: PairOut[];
}>(options?: {
    params?: ReviewQueueParams;
    query?: Omit<UseQueryOptions<{
        data: PairOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: reviewQueueKey(options?.params),
        queryFn: ()=>reviewQueue(options?.params),
        ...options?.query
    });
}
export function useReviewQueueSuspense<TData = {
    data: PairOut[];
}>(options?: {
    params?: ReviewQueueParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: PairOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: reviewQueueKey(options?.params),
        queryFn: ()=>reviewQueue(options?.params),
        ...options?.query
    });
}
export interface ReviewHistoryParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const reviewHistory = async (params?: ReviewHistoryParams, options?: RequestInit): Promise<{
    data: ReviewOut[];
}> =>{
    const res = await fetch("/api/reviews", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const reviewHistoryKey = (params?: ReviewHistoryParams)=>{
    return [
        "/api/reviews",
        params
    ] as const;
};
export function useReviewHistory<TData = {
    data: ReviewOut[];
}>(options?: {
    params?: ReviewHistoryParams;
    query?: Omit<UseQueryOptions<{
        data: ReviewOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: reviewHistoryKey(options?.params),
        queryFn: ()=>reviewHistory(options?.params),
        ...options?.query
    });
}
export function useReviewHistorySuspense<TData = {
    data: ReviewOut[];
}>(options?: {
    params?: ReviewHistoryParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: ReviewOut[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: reviewHistoryKey(options?.params),
        queryFn: ()=>reviewHistory(options?.params),
        ...options?.query
    });
}
export interface SaveReviewParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const saveReview = async (data: ReviewIn, params?: SaveReviewParams, options?: RequestInit): Promise<{
    data: ReviewOut;
}> =>{
    const res = await fetch("/api/reviews", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useSaveReview(options?: {
    mutation?: UseMutationOptions<{
        data: ReviewOut;
    }, ApiError, {
        params: SaveReviewParams;
        data: ReviewIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>saveReview(vars.data, vars.params),
        ...options?.mutation
    });
}
export interface SessionParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const session = async (params?: SessionParams, options?: RequestInit): Promise<{
    data: SessionOut;
}> =>{
    const res = await fetch("/api/session", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const sessionKey = (params?: SessionParams)=>{
    return [
        "/api/session",
        params
    ] as const;
};
export function useSession<TData = {
    data: SessionOut;
}>(options?: {
    params?: SessionParams;
    query?: Omit<UseQueryOptions<{
        data: SessionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: sessionKey(options?.params),
        queryFn: ()=>session(options?.params),
        ...options?.query
    });
}
export function useSessionSuspense<TData = {
    data: SessionOut;
}>(options?: {
    params?: SessionParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: SessionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: sessionKey(options?.params),
        queryFn: ()=>session(options?.params),
        ...options?.query
    });
}
export interface ReviewStatsParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const reviewStats = async (params?: ReviewStatsParams, options?: RequestInit): Promise<{
    data: StatsOut;
}> =>{
    const res = await fetch("/api/statistics", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const reviewStatsKey = (params?: ReviewStatsParams)=>{
    return [
        "/api/statistics",
        params
    ] as const;
};
export function useReviewStats<TData = {
    data: StatsOut;
}>(options?: {
    params?: ReviewStatsParams;
    query?: Omit<UseQueryOptions<{
        data: StatsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: reviewStatsKey(options?.params),
        queryFn: ()=>reviewStats(options?.params),
        ...options?.query
    });
}
export function useReviewStatsSuspense<TData = {
    data: StatsOut;
}>(options?: {
    params?: ReviewStatsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: StatsOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: reviewStatsKey(options?.params),
        queryFn: ()=>reviewStats(options?.params),
        ...options?.query
    });
}
export interface TrainingLabelsParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const trainingLabels = async (params?: TrainingLabelsParams, options?: RequestInit): Promise<{
    data: SnapshotOut;
}> =>{
    const res = await fetch("/api/training-labels", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const trainingLabelsKey = (params?: TrainingLabelsParams)=>{
    return [
        "/api/training-labels",
        params
    ] as const;
};
export function useTrainingLabels<TData = {
    data: SnapshotOut;
}>(options?: {
    params?: TrainingLabelsParams;
    query?: Omit<UseQueryOptions<{
        data: SnapshotOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: trainingLabelsKey(options?.params),
        queryFn: ()=>trainingLabels(options?.params),
        ...options?.query
    });
}
export function useTrainingLabelsSuspense<TData = {
    data: SnapshotOut;
}>(options?: {
    params?: TrainingLabelsParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: SnapshotOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: trainingLabelsKey(options?.params),
        queryFn: ()=>trainingLabels(options?.params),
        ...options?.query
    });
}
export interface MasteringGetOperationParams {
    domain_id: string;
    operation_id: string;
}
export const masteringGetOperation = async (params: MasteringGetOperationParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/operations/${params.operation_id}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const masteringGetOperationKey = (params?: MasteringGetOperationParams)=>{
    return [
        "/api/v1/domains/{domain_id}/operations/{operation_id}",
        params
    ] as const;
};
export function useMasteringGetOperation<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringGetOperationParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: masteringGetOperationKey(options.params),
        queryFn: ()=>masteringGetOperation(options.params),
        ...options?.query
    });
}
export function useMasteringGetOperationSuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringGetOperationParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: masteringGetOperationKey(options.params),
        queryFn: ()=>masteringGetOperation(options.params),
        ...options?.query
    });
}
export interface MasteringApproveParams {
    domain_id: string;
    operation_id: string;
}
export const masteringApprove = async (params: MasteringApproveParams, data: RevisionIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/operations/${params.operation_id}/approve`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringApprove(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringApproveParams;
        data: RevisionIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringApprove(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface MasteringOperationHistoryParams {
    domain_id: string;
    operation_id: string;
    limit?: number;
    after?: string | null;
}
export const masteringOperationHistory = async (params: MasteringOperationHistoryParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.limit != null) searchParams.set("limit", String(params?.limit));
    if (params?.after != null) searchParams.set("after", String(params?.after));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/v1/domains/${params.domain_id}/operations/${params.operation_id}/history?${queryString}` : `/api/v1/domains/${params.domain_id}/operations/${params.operation_id}/history`;
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const masteringOperationHistoryKey = (params?: MasteringOperationHistoryParams)=>{
    return [
        "/api/v1/domains/{domain_id}/operations/{operation_id}/history",
        params
    ] as const;
};
export function useMasteringOperationHistory<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringOperationHistoryParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: masteringOperationHistoryKey(options.params),
        queryFn: ()=>masteringOperationHistory(options.params),
        ...options?.query
    });
}
export function useMasteringOperationHistorySuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringOperationHistoryParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: masteringOperationHistoryKey(options.params),
        queryFn: ()=>masteringOperationHistory(options.params),
        ...options?.query
    });
}
export interface MasteringInboxParams {
    domain_id: string;
    state?: "open" | "claimed" | "resolved" | "canceled";
    limit?: number;
    after?: string | null;
}
export const masteringInbox = async (params: MasteringInboxParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.state != null) searchParams.set("state", String(params?.state));
    if (params?.limit != null) searchParams.set("limit", String(params?.limit));
    if (params?.after != null) searchParams.set("after", String(params?.after));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/v1/domains/${params.domain_id}/tasks?${queryString}` : `/api/v1/domains/${params.domain_id}/tasks`;
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const masteringInboxKey = (params?: MasteringInboxParams)=>{
    return [
        "/api/v1/domains/{domain_id}/tasks",
        params
    ] as const;
};
export function useMasteringInbox<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringInboxParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: masteringInboxKey(options.params),
        queryFn: ()=>masteringInbox(options.params),
        ...options?.query
    });
}
export function useMasteringInboxSuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringInboxParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: masteringInboxKey(options.params),
        queryFn: ()=>masteringInbox(options.params),
        ...options?.query
    });
}
export interface MasteringCreateTaskParams {
    domain_id: string;
}
export const masteringCreateTask = async (params: MasteringCreateTaskParams, data: CreateTaskIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringCreateTask(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringCreateTaskParams;
        data: CreateTaskIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringCreateTask(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface MasteringGetTaskParams {
    domain_id: string;
    task_id: string;
}
export const masteringGetTask = async (params: MasteringGetTaskParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks/${params.task_id}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const masteringGetTaskKey = (params?: MasteringGetTaskParams)=>{
    return [
        "/api/v1/domains/{domain_id}/tasks/{task_id}",
        params
    ] as const;
};
export function useMasteringGetTask<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringGetTaskParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: masteringGetTaskKey(options.params),
        queryFn: ()=>masteringGetTask(options.params),
        ...options?.query
    });
}
export function useMasteringGetTaskSuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringGetTaskParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: masteringGetTaskKey(options.params),
        queryFn: ()=>masteringGetTask(options.params),
        ...options?.query
    });
}
export interface MasteringCancelTaskParams {
    domain_id: string;
    task_id: string;
}
export const masteringCancelTask = async (params: MasteringCancelTaskParams, data: CancelIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/cancel`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringCancelTask(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringCancelTaskParams;
        data: CancelIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringCancelTask(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface MasteringClaimTaskParams {
    domain_id: string;
    task_id: string;
}
export const masteringClaimTask = async (params: MasteringClaimTaskParams, data: ClaimIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/claim`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringClaimTask(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringClaimTaskParams;
        data: ClaimIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringClaimTask(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface MasteringTaskHistoryParams {
    domain_id: string;
    task_id: string;
    limit?: number;
    after?: string | null;
}
export const masteringTaskHistory = async (params: MasteringTaskHistoryParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.limit != null) searchParams.set("limit", String(params?.limit));
    if (params?.after != null) searchParams.set("after", String(params?.after));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/history?${queryString}` : `/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/history`;
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const masteringTaskHistoryKey = (params?: MasteringTaskHistoryParams)=>{
    return [
        "/api/v1/domains/{domain_id}/tasks/{task_id}/history",
        params
    ] as const;
};
export function useMasteringTaskHistory<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringTaskHistoryParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: masteringTaskHistoryKey(options.params),
        queryFn: ()=>masteringTaskHistory(options.params),
        ...options?.query
    });
}
export function useMasteringTaskHistorySuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: MasteringTaskHistoryParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: masteringTaskHistoryKey(options.params),
        queryFn: ()=>masteringTaskHistory(options.params),
        ...options?.query
    });
}
export interface MasteringProposeParams {
    domain_id: string;
    task_id: string;
}
export const masteringPropose = async (params: MasteringProposeParams, data: ProposeIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/propose`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringPropose(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringProposeParams;
        data: ProposeIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringPropose(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface MasteringReleaseTaskParams {
    domain_id: string;
    task_id: string;
}
export const masteringReleaseTask = async (params: MasteringReleaseTaskParams, data: LeaseIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/release`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringReleaseTask(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringReleaseTaskParams;
        data: LeaseIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringReleaseTask(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface MasteringRenewTaskParams {
    domain_id: string;
    task_id: string;
}
export const masteringRenewTask = async (params: MasteringRenewTaskParams, data: RenewIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/v1/domains/${params.domain_id}/tasks/${params.task_id}/renew`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMasteringRenewTask(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: MasteringRenewTaskParams;
        data: RenewIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>masteringRenewTask(vars.params, vars.data),
        ...options?.mutation
    });
}
