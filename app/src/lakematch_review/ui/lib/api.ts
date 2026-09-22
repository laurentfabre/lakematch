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
