/**
 * Minimal smoke test to ensure the test runner works.
 * Replace with real component/integration tests as the frontend grows.
 */
describe('Smoke test', () => {
  it('should pass basic assertion', () => {
    expect(true).toBe(true);
  });

  it('should have NODE_ENV defined', () => {
    expect(process.env.NODE_ENV).toBeDefined();
  });
});
