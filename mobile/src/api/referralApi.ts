import { apiClient } from "./client";

/** Every number shown on the Refer & Earn screen comes from these responses. */
export interface ReferralProgram {
  enabled: boolean;
  referrer_reward: string;
  referred_reward: string;
  min_order_value: string;
  qualify_window_days: number;
  apply_window_days: number;
  currency: string;
}

export interface ReferralStats {
  total_referrals: number;
  pending: number;
  qualified: number;
  rewarded: number;
  reversed: number;
  cancelled: number;
  total_earned: string;
}

export interface ReferralMe {
  code: string | null;
  share_message: string | null;
  program: ReferralProgram;
  stats: ReferralStats;
  can_apply_code: boolean;
  already_referred: boolean;
  apply_blocked_reason: string | null;
}

export interface ReferralHistoryItem {
  id: number;
  referred_display_name: string;
  status: "PENDING" | "QUALIFIED" | "REWARDED" | "REVERSED" | "CANCELLED";
  applied_at: string;
  expires_at: string;
  qualified_at: string | null;
  rewarded_at: string | null;
  reward_amount: string | null;
}

export interface ReferralHistory {
  items: ReferralHistoryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApplyReferralResult {
  status: string;
  referrer_display_name: string;
  expires_at: string;
  referred_reward: string;
  min_order_value: string;
}

export const referralApi = {
  me: () => apiClient.get<ReferralMe>("/referrals/me").then((r) => r.data),
  history: () => apiClient.get<ReferralHistory>("/referrals/history").then((r) => r.data),
  apply: (code: string) =>
    apiClient.post<ApplyReferralResult>("/referrals/apply", { code }).then((r) => r.data),
};
