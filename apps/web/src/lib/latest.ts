// Each call to the returned function starts a request and returns a check that stays true
// only while no newer request has started, so late replies can be dropped.
export function latest(): () => () => boolean {
  let counter = 0;
  return () => {
    const ticket = ++counter;
    return () => ticket === counter;
  };
}
