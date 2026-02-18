const BASE = '/api';

/**
 * Perform a fetch and return parsed JSON. Throws if the response is not ok.
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function request(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  // 204 No Content — nothing to parse
  if (res.status === 204) return res;
  return res.json();
}

/**
 * Build fetch options for a request that sends a JSON body.
 * @param {string} method  HTTP verb
 * @param {object} body    Plain object to serialise as JSON
 * @returns {RequestInit}
 */
function jsonBody(method, body) {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

export const api = {
  // ---------------------------------------------------------------------------
  // Muscle groups
  // ---------------------------------------------------------------------------

  getMuscleGroups: () =>
    request(`${BASE}/muscle-groups`),

  createMuscleGroup: (name) =>
    request(`${BASE}/muscle-groups`, jsonBody('POST', { name })),

  renameMuscleGroup: (id, name) =>
    request(`${BASE}/muscle-groups/${id}`, jsonBody('PATCH', { name })),

  deleteMuscleGroup: (id) =>
    request(`${BASE}/muscle-groups/${id}`, { method: 'DELETE' }),

  // ---------------------------------------------------------------------------
  // Lifts
  // ---------------------------------------------------------------------------

  getLifts: () =>
    request(`${BASE}/lifts`),

  createLift: (name, muscleGroupIds) =>
    request(`${BASE}/lifts`, jsonBody('POST', {
      name,
      muscle_group_ids: muscleGroupIds,
    })),

  updateLift: (id, { name, muscleGroupIds }) =>
    request(`${BASE}/lifts/${id}`, jsonBody('PATCH', {
      ...(name !== undefined && { name }),
      ...(muscleGroupIds !== undefined && { muscle_group_ids: muscleGroupIds }),
    })),

  deleteLift: (id) =>
    request(`${BASE}/lifts/${id}`, { method: 'DELETE' }),

  // ---------------------------------------------------------------------------
  // Workouts
  // ---------------------------------------------------------------------------

  getWorkouts: () =>
    request(`${BASE}/workouts`),

  createWorkout: () =>
    request(`${BASE}/workouts`, { method: 'POST' }),

  getWorkout: (id) =>
    request(`${BASE}/workouts/${id}`),

  updateWorkout: (id, { subtitle }) =>
    request(`${BASE}/workouts/${id}`, jsonBody('PATCH', { subtitle })),

  deleteWorkout: (id) =>
    request(`${BASE}/workouts/${id}`, { method: 'DELETE' }),

  addLiftToWorkout: (workoutId, { liftId, displayOrder }) =>
    request(`${BASE}/workouts/${workoutId}/lifts`, jsonBody('POST', {
      lift_id: liftId,
      display_order: displayOrder,
    })),

  removeWorkoutLift: (workoutId, wlId) =>
    request(`${BASE}/workouts/${workoutId}/lifts/${wlId}`, { method: 'DELETE' }),

  suggestLift: (workoutId) =>
    request(`${BASE}/workouts/${workoutId}/suggest`, { method: 'POST' }),

  // ---------------------------------------------------------------------------
  // Sets
  // ---------------------------------------------------------------------------

  addSet: (wlId, { reps, weight }) =>
    request(`${BASE}/workout-lifts/${wlId}/sets`, jsonBody('POST', {
      reps,
      weight,
    })),

  updateSet: (setId, { reps, weight }) =>
    request(`${BASE}/sets/${setId}`, jsonBody('PATCH', {
      ...(reps !== undefined && { reps }),
      ...(weight !== undefined && { weight }),
    })),

  deleteSet: (setId) =>
    request(`${BASE}/sets/${setId}`, { method: 'DELETE' }),

  // ---------------------------------------------------------------------------
  // Settings
  // ---------------------------------------------------------------------------

  getConflicts: () =>
    request(`${BASE}/settings/conflicts`),

  addConflict: (muscleGroupAId, muscleGroupBId) =>
    request(`${BASE}/settings/conflicts`, jsonBody('POST', {
      muscle_group_a_id: muscleGroupAId,
      muscle_group_b_id: muscleGroupBId,
    })),

  deleteConflict: (id) =>
    request(`${BASE}/settings/conflicts/${id}`, { method: 'DELETE' }),

  // ---------------------------------------------------------------------------
  // Analytics
  // ---------------------------------------------------------------------------

  getProgress: () =>
    request(`${BASE}/analytics/progress`),

  getLiftHistory: (liftId) =>
    request(`${BASE}/analytics/lifts/${liftId}`),
};
